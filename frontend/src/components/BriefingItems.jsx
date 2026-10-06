// 피그마 컴포넌트 CategoryChip / HeadlineItem / EpisodeItem
import { Link } from 'react-router-dom'
import Icon from './Icon'
import { dateParts, formatClock, formatDuration } from '../utils/date'
import './BriefingItems.css'

export function CategoryChip({ label }) {
  return <span className="chip">{label}</span>
}

/** 오늘 방송 헤드라인 한 줄. 누르면 해당 시간으로 이동 */
export function HeadlineItem({ time, category, title, onSelect, active = false }) {
  return (
    <li>
      <button type="button" className={`headline${active ? ' is-active' : ''}`} onClick={() => onSelect?.(time)}>
        <span className="headline__time">{formatClock(time)}</span>
        <span className="headline__body">
          <CategoryChip label={category} />
          <span className="headline__title">{title}</span>
        </span>
      </button>
    </li>
  )
}

/** 지난 방송 목록 아이템 */
export function EpisodeItem({ briefing, onPlay }) {
  const { day, weekday } = dateParts(briefing.date)
  const cats = briefing.categories?.join(' · ')
  return (
    <li className="episode">
      <Link to={`/script/${briefing.date}`} className="episode__link">
        <span className="episode__date">
          <b>{String(day).padStart(2, '0')}</b>
          <small>{weekday}</small>
        </span>
        <span className="episode__body">
          <span className="episode__title">{briefing.title}</span>
          <span className="episode__meta">
            {formatDuration(briefing.duration)}
            {cats ? ` · ${cats}` : ''}
          </span>
        </span>
      </Link>
      <button type="button" className="episode__play" onClick={() => onPlay?.(briefing)} aria-label={`${briefing.date} 방송 재생`}>
        <Icon name="play" size={16} />
      </button>
    </li>
  )
}
