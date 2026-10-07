import Logo from './Logo'

/**
 * 첫 접속 시 오늘 방송 정보를 불러오는 동안만 잠깐 보여주는 로딩 화면.
 * 데이터가 오면 바로 사라져요 (Zero-Friction 원칙).
 */
export default function SplashScreen() {
  return (
    <div className="splash" role="status" aria-live="polite">
      <div className="splash__glow" />
      <Logo variant="symbol" size={96} animate />
      <p className="splash__word">
        <b>Dawn</b>
        <span>Air</span>
      </p>
      <p className="splash__tag">오늘 아침, 귀로 듣는 브리핑</p>
      <span className="splash__bar">
        <span />
      </span>
      <span className="visually-hidden">오늘 방송을 불러오는 중이에요</span>
    </div>
  )
}
