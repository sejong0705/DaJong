// 피그마 PlayerBar(데스크톱) / MiniPlayer(모바일)
// 화면 아래에 고정된 재생바. 누르면 방송 화면(/player)이 열려요.
import { Link, useNavigate } from 'react-router-dom'
import Icon from './Icon'
import { usePlayer } from '../context/PlayerContext'
import { dateParts, formatClock, formatRate } from '../utils/date'
import './PlayerDock.css'

export default function PlayerDock() {
  const { briefing, isPlaying, currentTime, duration, rate, toggle, skip, seek, cycleRate, error } = usePlayer()
  const navigate = useNavigate()
  if (!briefing) return null

  const total = duration || briefing.duration || 0
  const progress = total ? (currentTime / total) * 100 : 0
  const { month, day } = dateParts(briefing.date)
  const label = `${month}월 ${day}일 모닝 브리핑`

  const onSeek = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    seek(((e.clientX - rect.left) / rect.width) * total)
  }

  return (
    <div className="player-dock" role="region" aria-label="오디오 플레이어">
      <div className="player-dock__inner container">
        <div className="player-dock__controls">
          <button type="button" className="only-desktop" onClick={() => skip(-15)} aria-label="15초 뒤로">
            <Icon name="rewind" size={22} />
          </button>
          <button type="button" className="player-dock__play" onClick={toggle} aria-label={isPlaying ? '일시정지' : '재생'}>
            <Icon name={isPlaying ? 'pause' : 'play'} size={20} />
          </button>
          <button type="button" className="only-desktop" onClick={() => skip(15)} aria-label="15초 앞으로">
            <Icon name="forward" size={22} />
          </button>
        </div>

        <button type="button" className="player-dock__info" onClick={() => navigate('/player')} aria-label="방송 화면 열기">
          <span className="player-dock__title">
            {label}
            <span className="only-desktop"> · {briefing.title}</span>
          </span>
          <span className="player-dock__progress-row">
            <span className="only-desktop">{formatClock(currentTime)}</span>
            <span
              className="player-dock__track"
              onClick={(e) => {
                e.stopPropagation()
                onSeek(e)
              }}
            >
              <span className="player-dock__bar" style={{ width: `${progress}%` }} />
            </span>
            <span className="only-desktop">{formatClock(total)}</span>
          </span>
          <span className="player-dock__time only-mobile">
            {error ? error : `${formatClock(currentTime)} / ${formatClock(total)}`}
          </span>
        </button>

        <div className="player-dock__actions only-desktop">
          <button type="button" className="pill" onClick={cycleRate}>
            {formatRate(rate)}
          </button>
          <Link to={`/script/${briefing.date}`} className="pill">
            대본 보기
          </Link>
        </div>
      </div>
    </div>
  )
}
