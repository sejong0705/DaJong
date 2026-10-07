import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { PlayerProvider } from './context/PlayerContext'
import AppLayout from './components/AppLayout'
import TodayPage from './pages/TodayPage'
import ScriptPage from './pages/ScriptPage'
import HistoryPage from './pages/HistoryPage'
import PlayerPage from './pages/PlayerPage'

/*
 * 화면 구성 (피그마 와이어프레임 번호)
 *   /                 01 홈 - 오늘의 브리핑 (04 방송 준비 중, 05 로딩 포함)
 *   /script/:date     02 대본 보기
 *   /history          03 지난 방송
 *   /player           06 방송 화면 (헤더·탭바 없이 전체 화면)
 */
export default function App() {
  return (
    <BrowserRouter>
      <PlayerProvider>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<TodayPage />} />
            <Route path="script" element={<ScriptPage />} />
            <Route path="script/:date" element={<ScriptPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="*" element={<TodayPage />} />
          </Route>
          <Route path="player" element={<PlayerPage />} />
        </Routes>
      </PlayerProvider>
    </BrowserRouter>
  )
}
