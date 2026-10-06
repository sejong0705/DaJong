// 피그마 TopNav(데스크톱) / BottomNav(모바일)
// 768px 기준으로 CSS 에서 둘 중 하나만 보여요.
import { Link, NavLink } from 'react-router-dom'
import Icon from './Icon'
import Logo from './Logo'
import { formatLongDate, todayKey } from '../utils/date'
import './Navigation.css'

const LINKS = [
  { to: '/', label: '오늘의 브리핑', short: '오늘', icon: 'home', end: true },
  { to: '/history', label: '지난 방송', short: '지난 방송', icon: 'calendar' },
]

export function TopNav({ theme, onToggleTheme }) {
  const year = todayKey().slice(0, 4)
  return (
    <header className="topnav">
      <div className="topnav__inner container">
        <div className="topnav__left">
          <Link to="/" aria-label="DawnAir 홈">
            <Logo />
          </Link>
          <nav className="topnav__links" aria-label="주요 메뉴">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end} className="topnav__link">
                {l.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="topnav__right">
          <span className="topnav__date">
            {year}년 {formatLongDate(todayKey())}
          </span>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </div>
    </header>
  )
}

export function BottomNav() {
  return (
    <nav className="bottomnav" aria-label="주요 메뉴">
      {LINKS.map((l) => (
        <NavLink key={l.to} to={l.to} end={l.end} className="bottomnav__tab">
          <Icon name={l.icon} size={22} />
          <span>{l.short}</span>
        </NavLink>
      ))}
    </nav>
  )
}

export function ThemeToggle({ theme, onToggle }) {
  const dark = theme === 'dark'
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={onToggle}
      aria-label={dark ? '라이트 모드로 바꾸기' : '다크 모드로 바꾸기'}
      title={dark ? '라이트 모드' : '다크 모드'}
    >
      <Icon name={dark ? 'sun' : 'moon'} size={20} />
    </button>
  )
}
