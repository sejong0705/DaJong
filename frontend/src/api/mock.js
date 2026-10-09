// 백엔드 없이 화면을 확인할 때 쓰는 목업이에요 (.env 의 VITE_API_BASE_URL 이 비어 있을 때).
// get_briefing Lambda 응답과 같은 형태 { meta, script } 를 돌려줘요.

import { addDays, currentHourKST, formatLongDate, todayKey } from '../utils/date'

const TITLES = [
  '금리 동결, 반도체 반등… 오늘 아침 꼭 알아야 할 소식',
  '금리 결정 앞두고… 이번 주 시장 체크포인트',
  '주말 사이 달라진 것들: 유가와 환율',
  'AI 스마트폰 경쟁, 하반기 승자는?',
]

const NEWS = [
  {
    category: '오늘의 톱뉴스',
    headline: '기준금리 동결',
    points: ['한국은행이 기준금리를 동결했습니다.', '물가는 안정세지만 가계부채 증가세가 부담이라는 판단입니다.'],
    background: '가계부채가 빠르게 늘면서 금리 인하에 신중해졌습니다.',
    why_it_matters: '대출 금리 인하를 기다리던 분들에겐 조금 더 시간이 필요하다는 신호입니다.',
  },
  {
    category: 'IT/과학',
    headline: '반도체 수출 3개월 연속 증가',
    points: ['반도체 수출이 석 달째 늘었습니다.', '인공지능 서버용 메모리 수요가 증가를 이끌었습니다.'],
    background: '인공지능 투자가 늘면서 고대역폭메모리 수요가 커졌습니다.',
    why_it_matters: '수출 회복이 내수 경기로 이어질지가 다음 관전 포인트입니다.',
  },
  {
    category: '국제',
    headline: '유럽 인공지능 규제법 시행',
    points: ['유럽연합의 인공지능 규제법이 본격 시행에 들어갔습니다.', '위험 등급에 따라 기업의 의무가 달라집니다.'],
    background: '유럽연합은 2024년 세계 첫 포괄적 인공지능 법을 통과시켰습니다.',
    why_it_matters: '유럽에 서비스하는 국내 기업도 대응 준비가 필요합니다.',
  },
]

function makeScript(date, i) {
  const segments = NEWS.map((n, k) => {
    const lead = k === 0 ? '오늘의 톱뉴스입니다.' : `${n.category.replace('/', ', ')} 소식입니다.`
    return {
      id: k === 0 ? 'top' : `s${k}`,
      type: k === 0 ? 'top' : 'news',
      ...n,
      sources: [{ press: 'example.com', title: n.headline, link: 'https://example.com' }],
      speech: `${lead} ${n.headline}. ${n.points.join(' ')}`,
    }
  })
  return {
    date,
    date_label: formatLongDate(date),
    title: TITLES[i % TITLES.length],
    opening: { speech: `좋은 아침입니다. ${formatLongDate(date)}, 던에어입니다. 오늘의 주요 소식 전해드릴게요.` },
    weather: {
      seoul: {
        name: '서울', temp_min: 12, temp_max: 23, pop: 20,
        summary: '맑음, 일교차 큼', outfit: '얇은 겉옷',
        speech: '오늘의 날씨입니다. 서울은 아침 12도로 쌀쌀하게 시작해 낮에는 23도까지 오르겠습니다. 얇은 겉옷 하나 챙기시면 좋겠어요.',
      },
    },
    segments,
    closing: { speech: '오늘도 좋은 하루 보내세요. 던에어였습니다.' },
  }
}

/** 오늘 포함 최근 20일치 (오전 6시 이전이면 오늘 방송은 아직 없음) */
function allDates() {
  const today = todayKey()
  const from = currentHourKST() >= 6 ? 0 : 1
  return Array.from({ length: 20 - from }, (_, k) => addDays(today, -(k + from)))
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms))

export async function mockGet(date) {
  await wait(250)
  const i = allDates().indexOf(date)
  if (i < 0) return null
  const script = makeScript(date, i)
  return { meta: { date, title: script.title }, script }
}

export async function mockList() {
  await wait(200)
  return allDates().map((date, i) => ({ date, title: TITLES[i % TITLES.length], duration: 180 }))
}
