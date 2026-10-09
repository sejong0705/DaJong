// 브리핑 데이터 조회
//
// 백엔드: get_briefing Lambda (함수 URL)
//   GET {API}                 오늘 방송 (없으면 가장 최근 방송)
//   GET {API}?date=YYYY-MM-DD → { meta, script }   (없으면 404)
//   GET {API}?list=1          → { items: [{ date, date_label, title, duration, segmentCount }] }
//
// .env 의 VITE_API_BASE_URL 이 비어 있으면 src/api/mock.js 의 목업(같은 형태)을 써요.
//
// 백엔드 응답(script.json)을 화면에서 쓰는 형태로 바꿔서 돌려줍니다.
//   briefing : { date, title, duration, weather, weatherSummary, headlines[{time, category, title}], categories, timeline }
//   script   : { date, segments[{ start, category, title, text, points, background, why, sources }] }
// 음성은 브라우저 speechSynthesis 가 timeline 의 문장들을 읽어요 (PlayerContext 참고).

import { mockGet, mockList } from './mock'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export const isMock = !API_BASE

/** 사용자 지역 key. 지역 선택 기능이 생기면 여기만 바꾸면 돼요 */
export const DEFAULT_REGION = 'seoul'

/** 한국어 TTS 대략적인 읽기 속도 (글자/초). 백엔드 duration_estimate 와 같은 기준 */
const CHARS_PER_SEC = 7

async function getJson(url) {
  const res = await fetch(url)
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`요청 실패 (${res.status})`)
  return res.json()
}

// ---------------------------------------------------------------- 원본 조회 (날짜별 캐시)
const rawCache = new Map()

/** { meta, script } 또는 null. 같은 날짜는 한 번만 요청 */
function fetchRaw(date) {
  if (!rawCache.has(date)) {
    const p = isMock ? mockGet(date) : getJson(`${API_BASE}/?date=${date}`)
    rawCache.set(date, p.catch((e) => {
      rawCache.delete(date) // 실패한 요청은 다음에 다시 시도
      throw e
    }))
  }
  return rawCache.get(date)
}

let listCache = null
function fetchList() {
  if (!listCache) {
    listCache = (isMock ? mockList() : getJson(`${API_BASE}/?list=1`).then((d) => d?.items ?? [])).catch((e) => {
      listCache = null
      throw e
    })
  }
  return listCache
}

// ---------------------------------------------------------------- 대본 → 타임라인
// mp3 가 없으니 글자 수로 '가상 재생 시간'을 만들어요.
// 챕터 · 진행바 · 대본 하이라이트가 모두 이 시간을 기준으로 움직입니다.

function splitSentences(text = '') {
  return text
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

/**
 * script.json → 재생 순서대로 나눈 파트 목록
 * parts: [{ key, category, title, start, end, sentences: [{ text, start, end }], segment? }]
 */
export function buildTimeline(script, region = DEFAULT_REGION) {
  const weather = script.weather?.[region] ?? Object.values(script.weather ?? {})[0]
  const raw = [
    { key: 'opening', category: '오프닝', title: '오프닝', text: script.opening?.speech },
    weather && { key: 'weather', category: '날씨', title: weather.summary || `${weather.name} 날씨`, text: weather.speech },
    ...(script.segments ?? []).map((s) => ({ key: s.id, category: s.category, title: s.headline, text: s.speech, segment: s })),
    { key: 'closing', category: '클로징', title: '클로징', text: script.closing?.speech },
  ].filter((p) => p && p.text)

  let t = 0
  const parts = raw.map((p) => {
    const start = t
    const sentences = splitSentences(p.text).map((text) => {
      const s = { text, start: t, end: t + text.length / CHARS_PER_SEC }
      t = s.end
      return s
    })
    return { ...p, start, end: t, sentences }
  })
  return { parts, total: t }
}

// ---------------------------------------------------------------- 화면용 형태로 변환
function toBriefing(meta, script) {
  const region = script.weather?.[DEFAULT_REGION] ? DEFAULT_REGION : Object.keys(script.weather ?? {})[0]
  const w = script.weather?.[region]
  const timeline = buildTimeline(script, region)
  const news = timeline.parts.filter((p) => p.segment)
  return {
    date: script.date,
    title: script.title ?? meta?.title,
    duration: Math.round(timeline.total),
    weather: w && { region: w.name, sky: w.summary, min: w.temp_min, max: w.temp_max, rainProb: w.pop },
    weatherSummary: w?.outfit ?? '',
    headlines: timeline.parts
      .filter((p) => p.key === 'weather' || p.segment)
      .map((p) => ({ time: p.start, category: p.category, title: p.title })),
    categories: [...new Set(news.map((p) => p.category).filter((c) => c !== '오늘의 톱뉴스'))],
    timeline, // PlayerContext 가 읽어요
  }
}

function toScript(script, timeline) {
  return {
    date: script.date,
    segments: timeline.parts.map((p) => ({
      start: p.start,
      category: p.category,
      title: p.title,
      // 뉴스는 핵심 요약(points), 나머지는 읽는 문장 그대로
      text: p.segment ? '' : p.text,
      points: p.segment?.points ?? [],
      background: p.segment?.background ?? '',
      why: p.segment?.why_it_matters ?? '',
      sources: p.segment?.sources ?? [],
    })),
  }
}

// ---------------------------------------------------------------- 페이지에서 쓰는 함수 (기존 이름 유지)
export async function getBriefing(date) {
  const raw = await fetchRaw(date)
  return raw ? toBriefing(raw.meta, raw.script) : null
}

/** 해당 월(YYYY-MM)의 방송 목록. 목록 API 는 전체를 한 번 받아서 월별로 나눠요 */
export async function listBriefings(month) {
  const items = await fetchList()
  return items
    .filter((b) => b.date.startsWith(month))
    .map((b) => ({ date: b.date, title: b.title, duration: b.duration, categories: [] }))
}

export async function getScript(date) {
  const raw = await fetchRaw(date)
  if (!raw) return null
  const briefing = toBriefing(raw.meta, raw.script)
  return toScript(raw.script, briefing.timeline)
}
