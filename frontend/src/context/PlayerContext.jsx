import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useAudioAnalyser } from '../hooks/useAudioAnalyser'

/**
 * 앱 전체에서 하나의 오디오 플레이어를 공유해요.
 * 홈 → 대본 → 방송 화면으로 이동해도 재생이 끊기지 않습니다.
 */
const PlayerContext = createContext(null)

const RATES = [1, 1.25, 1.5, 0.8]

export function PlayerProvider({ children }) {
  // <audio> 는 DOM 에 붙이지 않아도 재생돼요
  const [audio] = useState(() => {
    const el = new Audio()
    el.preload = 'metadata'
    el.crossOrigin = 'anonymous' // AnalyserNode 로 볼륨을 읽으려면 필요 (useAudioAnalyser 주석 참고)
    return el
  })
  const { connect, getLevel } = useAudioAnalyser(audio)

  const [briefing, setBriefing] = useState(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [rate, setRateState] = useState(1)
  const [error, setError] = useState(null)

  useEffect(() => {
    const on = (type, fn) => audio.addEventListener(type, fn)
    const off = (type, fn) => audio.removeEventListener(type, fn)
    const handlers = {
      play: () => setIsPlaying(true),
      pause: () => setIsPlaying(false),
      ended: () => setIsPlaying(false),
      timeupdate: () => setCurrentTime(audio.currentTime),
      loadedmetadata: () => setDuration(audio.duration || 0),
      error: () => {
        setIsPlaying(false)
        setError('오디오를 불러오지 못했어요.')
      },
    }
    Object.entries(handlers).forEach(([t, fn]) => on(t, fn))
    return () => Object.entries(handlers).forEach(([t, fn]) => off(t, fn))
  }, [audio])

  const play = useCallback(() => {
    connect() // 사용자 클릭 안에서 AudioContext 를 시작해야 해요
    setError(null)
    audio.play().catch(() => setError('재생을 시작하지 못했어요.'))
  }, [audio, connect])

  const pause = useCallback(() => audio.pause(), [audio])

  /** 브리핑을 플레이어에 올리기. 같은 브리핑이면 그대로 둠 */
  const load = useCallback(
    (next, { autoplay = false } = {}) => {
      if (!next) return
      if (!briefing || briefing.date !== next.date) {
        audio.src = next.audioUrl
        audio.playbackRate = rate
        setBriefing(next)
        setCurrentTime(0)
        setDuration(next.duration || 0)
      }
      if (autoplay) play()
    },
    [audio, briefing, play, rate],
  )

  const toggle = useCallback(() => (audio.paused ? play() : pause()), [audio, play, pause])

  const seek = useCallback(
    (sec) => {
      // 방금 load() 한 직후엔 메타데이터가 없어서 duration 이 NaN 이에요 → 이때는 위쪽 제한 없이 둠
      const max = Number.isFinite(audio.duration) ? audio.duration : Infinity
      const t = Math.min(Math.max(0, sec), max)
      audio.currentTime = t
      // 일부 브라우저(Safari)는 메타데이터 전에 바꾼 위치를 무시해서, 로드되면 한 번 더 맞춰요
      if (audio.readyState === 0) {
        audio.addEventListener('loadedmetadata', () => (audio.currentTime = t), { once: true })
      }
      setCurrentTime(t)
    },
    [audio],
  )

  const skip = useCallback((delta) => seek(audio.currentTime + delta), [audio, seek])

  const cycleRate = useCallback(() => {
    const next = RATES[(RATES.indexOf(rate) + 1) % RATES.length]
    audio.playbackRate = next
    setRateState(next)
  }, [audio, rate])

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
