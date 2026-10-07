import { useId } from 'react'
import './Logo.css'

/**
 * DawnAir 로고
 *   variant="full"   → 마크 + 워드마크 (헤더용)
 *   variant="symbol" → 마크만
 *   animate          → orb → 안쪽 전파 → 바깥쪽 전파 순서로 등장 (피그마 LogoIntro 와 같은 타이밍)
 */
export default function Logo({ variant = 'full', size = 36, animate = false, className = '' }) {
  const id = useId().replace(/:/g, '')

  const mark = (
    <svg
      className={`logo-mark${animate ? ' is-animated' : ''}`}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      aria-hidden="true"
    >
      <defs>
        <radialGradient id={`orb-${id}`} cx="0.36" cy="0.32" r="0.75">
          <stop offset="0" stopColor="var(--orb-1)" />
          <stop offset="0.42" stopColor="var(--orb-2)" />
          <stop offset="0.8" stopColor="var(--orb-3)" />
          <stop offset="1" stopColor="var(--orb-4)" />
        </radialGradient>
        <filter id={`blur-${id}`} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" />
        </filter>
      </defs>
      <path className="logo-wave logo-wave--outer" d="M2.5 28a21.5 21.5 0 0 1 43 0" />
      <path className="logo-wave logo-wave--inner" d="M8 28a16 16 0 0 1 32 0" />
      <circle className="logo-glow" cx="24" cy="30" r="13" filter={`url(#blur-${id})`} />
      <circle className="logo-orb" cx="24" cy="29" r="10.5" fill={`url(#orb-${id})`} />
    </svg>
  )

  if (variant === 'symbol') return <span className={`logo ${className}`}>{mark}</span>

  return (
    <span className={`logo ${className}`} aria-label="DawnAir">
      {mark}
      <span className="logo-word" aria-hidden="true">
        <b>Dawn</b>
        <span>Air</span>
      </span>
    </span>
  )
}
