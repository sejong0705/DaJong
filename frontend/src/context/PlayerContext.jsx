import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { getBriefing } from '../api/briefing'

/**
 * 앱 전체에서 하나의 플레이어를 공유해요.
 * 홈 → 대본 → 방송 화면으로 이동해도 재생이 끊기지 않습니다.
 *
 * mp3 대신 브라우저 음성 합성(speechSynthesis)으로 대본을 문장 단위로 읽어요.
 * - briefing.timeline 의 문장마다 글자 수로 추정한 시작/끝 시간이 있어서,
 *   진행바 · 챕터 · 15초 이동 같은 기존 화면 기능을 그대로 쓸 수 있습니다.
 * - 문장 단위로 끊어 읽는 이유: 긴 문장을 한 번에 넣으면 크롬에서 중간에 멈추는 문제가 있어요.
 * - 일시정지는 '현재 문장 처음부터 다시 읽기' 방식이에요 (speechSynthesis.pause 는 브라우저마다 불안정).
 */
const PlayerContext = createContext(null)

const RATES = [1, 1.25, 1.5, 0.8]
const synth = typeof window !== 'undefined' ? window.speechSynthesis : null

/** 한국어 목소리 고르기 (자연스러운 목소리 우선) */
function pickVoice() {
  const ko = (synth?.getVoices() ?? []).filter((v) => v.lang?.toLowerCase().startsWith('ko'))
  return ko.find((v) => /Google|SunHi|Heami|Yuna|InJoon/i.test(v.name)) ?? ko[0] ?? null
}

/** 시간(초)에 해당하는 문장 번호 */
function indexAt(sentences, t) {
  let i = 0
  while (i + 1 < sentences.length && sentences[i + 1].start <= t) i++
  return i
}

export function PlayerProvider({ children }) {
  const [briefing, setBriefing] = useState(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [rate, setRateState] = useState(1)
  const [error, setError] = useState(null)

  // 화면에서 load() → seek() → play() 를 연달아 부르는 경우가 있어서, 최신 값은 ref 로 들고 있어요
  const briefingRef = useRef(null)
  const sentencesRef = useRef([])
  const timeRef = useRef(0)
  const rateRef = useRef(1)
  const playingRef = useRef(false)
  const sessionRef = useRef(0) // 취소된 문장의 onend 를 무시하기 위한 번호
  const speakingRef = useRef(false) // orb 용: 지금 소리가 나는 중인지
  const clockRef = useRef(null) // { base, at, end } 현재 문장의 시작 시간 · 시작 시각 · 끝 시간

  const setTime = useCallback((t) => {
    timeRef.current = t
    setCurrentTime(t)
  }, [])

  const stopSpeech = useCallback(() => {
    sessionRef.current++
    speakingRef.current = false
    clockRef.current = null
    synth?.cancel()
  }, [])

  /** i 번째 문장부터 끝까지 이어서 읽기 */
  const speakFrom = useCallback(
    (i) => {
      stopSpeech()
      const list = sentencesRef.current
      if (i >= list.length) {
        // 끝까지 다 읽음
        playingRef.current = false
        setIsPlaying(false)
        setTime(briefingRef.current?.timeline.total ?? 0)
        return
      }
      const s = list[i]
      const session = sessionRef.current
      setTime(s.start)
      clockRef.current = { base: s.start, at: performance.now(), end: s.end }

      const u = new SpeechSynthesisUtterance(s.text)
      u.lang = 'ko-KR'
      u.rate = rateRef.current
      const voice = pickVoice()
      if (voice) u.voice = voice
      u.onstart = () => {
        if (session !== sessionRef.current) return
        speakingRef.current = true
        clockRef.current = { base: s.start, at: performance.now(), end: s.end }
      }
      u.onend = () => {
        if (session !== sessionRef.current) return
        speakingRef.current = false
        speakFrom(i + 1)
      }
      u.onerror = (e) => {
        if (session !== sessionRef.current || e.error === 'interrupted' || e.error === 'canceled') return
        playingRef.current = false
        speakingRef.current = false
        setIsPlaying(false)
        setError(e.error === 'not-allowed' ? '재생 버튼을 한 번 더 눌러 주세요.' : '음성을 재생하지 못했어요.')
      }
      // cancel() 직후 바로 speak() 하면 일부 브라우저에서 무시돼서 한 박자 쉬어요
      setTimeout(() => session === sessionRef.current && synth.speak(u), 0)
    },
    [setTime, stopSpeech],
  )

  // 재생 중에는 현재 문장 안에서 시간을 흘려서 진행바가 부드럽게 움직이게 해요
  useEffect(() => {
    if (!isPlaying) return
    const id = setInterval(() => {
      const c = clockRef.current
      if (!c || !speakingRef.current) return
      const t = Math.min(c.end, c.base + ((performance.now() - c.at) / 1000) * rateRef.current)
      setTime(t)
    }, 200)
    return () => clearInterval(id)
  }, [isPlaying, setTime])

  // 페이지를 떠나면 읽던 음성도 멈춤
  useEffect(() => {
    const stop = () => synth?.cancel()
    window.addEventListener('beforeunload', stop)
    return () => {
      window.removeEventListener('beforeunload', stop)
      stop()
    }
  }, [])

  const play = useCallback(() => {
    if (!synth) {
      setError('이 브라우저는 음성 재생을 지원하지 않아요.')
      return
    }
    const list = sentencesRef.current
    if (!list.length) return
    setError(null)
    playingRef.current = true
    setIsPlaying(true)
    const total = briefingRef.current?.timeline.total ?? 0
    const t = timeRef.current >= total - 0.5 ? 0 : timeRef.current // 끝까지 들었으면 처음부터
    speakFrom(indexAt(list, t))
  }, [speakFrom])

  const pause = useCallback(() => {
    stopSpeech()
    playingRef.current = false
    setIsPlaying(false)
  }, [stopSpeech])

  /** 브리핑을 플레이어에 올리기. 같은 브리핑이면 그대로 둠 */
  const load = useCallback(
    (next, { autoplay = false } = {}) => {
      if (!next) return
      // 지난 방송 목록 아이템처럼 대본이 없는 경우 전체를 받아와서 다시 load
      if (!next.timeline) {
        getBriefing(next.date)
          .then((full) => full && load(full, { autoplay }))
          .catch(() => setError('방송을 불러오지 못했어요.'))
        return
      }
      if (briefingRef.current?.date !== next.date) {
        stopSpeech()
        playingRef.current = false
        setIsPlaying(false)
        briefingRef.current = next
        sentencesRef.current = next.timeline.parts.flatMap((p) => p.sentences)
        setBriefing(next)
        setTime(0)
        setDuration(next.timeline.total)
      }
      if (autoplay) play()
    },
    [play, setTime, stopSpeech],
  )

  const toggle = useCallback(() => (playingRef.current ? pause() : play()), [pause, play])

  const seek = useCallback(
    (sec) => {
      const total = briefingRef.current?.timeline.total ?? 0
      const t = Math.min(Math.max(0, sec), total)
      if (playingRef.current) speakFrom(indexAt(sentencesRef.current, t))
      else setTime(t)
    },
    [setTime, speakFrom],
  )

  const skip = useCallback((delta) => seek(timeRef.current + delta), [seek])

  const cycleRate = useCallback(() => {
    const next = RATES[(RATES.indexOf(rateRef.current) + 1) % RATES.length]
    rateRef.current = next
    setRateState(next)
    // 읽는 중이면 지금 문장부터 새 속도로 다시 읽기
    if (playingRef.current) speakFrom(indexAt(sentencesRef.current, timeRef.current))
  }, [speakFrom])

  /** orb 용 목소리 크기(0~1). 실제 볼륨은 읽을 수 없어서, 말하는 동안 사인파 + 약간의 흔들림으로 만들어요 */
  const getLevel = useCallback(() => {
    if (!speakingRef.current) return 0
    const t = performance.now() / 1000
    const v = 0.55 + 0.2 * Math.sin(t * 7) + 0.12 * Math.sin(t * 13.3 + 1) + (Math.random() - 0.5) * 0.12
    return Math.min(1, Math.max(0, v))
  }, [])

  const value = useMemo(
    () => ({ briefing, isPlaying, currentTime, duration, rate, error, load, play, pause, toggle, seek, skip, cycleRate, getLevel }),
    [briefing, isPlaying, currentTime, duration, rate, error, load, play, pause, toggle, seek, skip, cycleRate, getLevel],
  )

  return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>
}

export function usePlayer() {
  const ctx = useContext(PlayerContext)
  if (!ctx) throw new Error('usePlayer 는 PlayerProvider 안에서만 쓸 수 있어요')
  return ctx
}
