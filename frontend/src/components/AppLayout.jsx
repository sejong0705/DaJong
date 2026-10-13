import { useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { BottomNav, TopNav } from './Navigation'
import PlayerDock from './PlayerDock'
import { usePlayer } from '../context/PlayerContext'
import { useTheme } from '../hooks/useTheme'

/** 상단 헤더 + 본문 + 하단 재생바 + (모바일) 하단 탭바 */
export default function AppLayout() {
  const { theme, toggle } = useTheme()
  const { briefing } = usePlayer()
  const { pathname } = useLocation()

  // BrowserRouter 는 스크롤을 되돌려주지 않아서, 페이지가 바뀌면 맨 위로 올려요
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <div className={`app${briefing ? ' has-player' : ''}`}>
      <TopNav theme={theme} onToggleTheme={toggle} />
      <main className="app-main">
        <Outlet />
      </main>
      <PlayerDock />
      <BottomNav />
    </div>
  )
}
