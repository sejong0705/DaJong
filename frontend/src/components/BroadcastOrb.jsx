import { useEffect, useRef } from 'react'
import { usePlayer } from '../context/PlayerContext'
import './BroadcastOrb.css'

/**
 * 방송 화면의 태양(orb)
 *
 * 재생 중에는 AnalyserNode 로 읽은 목소리 볼륨(0~1)을 glow 의 크기 · 밝기 · 움직임 폭에 반영해요.
 * React 상태를 매 프레임 바꾸면 느려지니까, CSS 변수만 직접 갱신합니다.
 *   --level : 볼륨 (glow 크기와 밝기)
 *   --dx/--dy, --rx/--ry : glow 두 겹이 천천히 떠다니는 위치 (볼륨이 클수록 크게 움직임)
 */
/** size 를 주지 않으면 CSS 변수 --size 를 따라요 (화면 크기별 크기는 CSS 에서) */
export default function BroadcastOrb({ size }) {
  const { isPlaying, getLevel } = usePlayer()
  const ref = useRef(null)
  const playingRef = useRef(isPlaying)
  playingRef.current = isPlaying

  useEffect(() => {
    const el = ref.current
    if (!el) return
    let raf
    let level = 0
    const start = performance.now()

    const tick = (now) => {
      const target = playingRef.current ? getLevel() : 0
      // 부드럽게 따라가기 (커질 땐 빠르게, 작아질 땐 천천히)
      level += (target - level) * (target > level ? 0.25 : 0.06)

      const t = (now - start) / 1000
      const amp = playingRef.current ? 6 + level * 14 : 0
      el.style.setProperty('--level', level.toFixed(3))
      el.style.setProperty('--dx', (Math.sin(t * 0.6) * amp).toFixed(2) + 'px')
      el.style.setProperty('--dy', (Math.cos(t * 0.45) * amp * 0.8).toFixed(2) + 'px')
      el.style.setProperty('--rx', (Math.sin(t * 0.5 + 2) * -amp * 1.2).toFixed(2) + 'px')
      el.style.setProperty('--ry', (Math.cos(t * 0.7 + 1) * amp).toFixed(2) + 'px')

      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [getLevel])

  return (
    <div
      ref={ref}
      className={`broadcast-orb${isPlaying ? ' is-playing' : ''}`}
      style={size ? { '--size': `${size}px` } : undefined}
      aria-hidden="true"
    >
      <div className="broadcast-orb__glow" />
      <div className="broadcast-orb__glow broadcast-orb__glow--rose" />
      <div className="broadcast-orb__core" />
    </div>
  )
}
