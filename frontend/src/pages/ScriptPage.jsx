// 02 대본 보기
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Icon from '../components/Icon'
import { CategoryChip } from '../components/BriefingItems'
import { getBriefing, getScript } from '../api/briefing'
import { useAsync } from '../hooks/useAsync'
import { usePlayer } from '../context/PlayerContext'
import { dateParts, formatClock, todayKey } from '../utils/date'
import './pages.css'

export default function ScriptPage() {
  const { date = todayKey() } = useParams()
  const { data, loading } = useAsync(async () => {
    const [briefing, script] = await Promise.all([getBriefing(date), getScript(date)])
    return { briefing, script }
  }, [date])
  // 필터는 날짜별로 기억해서, 다른 날짜로 넘어가면 '전체'로 돌아가요
  const [picked, setPicked] = useState({ date, value: '전체' })
  const filter = picked.date === date ? picked.value : '전체'
  const setFilter = (value) => setPicked({ date, value })
  const player = usePlayer()

  const segments = useMemo(() => data?.script?.segments ?? [], [data])
  const categories = useMemo(() => ['전체', ...new Set(segments.map((s) => s.category))], [segments])

  if (loading) return <div className="container page text-secondary">대본을 불러오는 중…</div>
  if (!data?.briefing || !data?.script) {
    return (
      <div className="container page">
        <div className="card empty-state">
          <h1>이 날짜의 방송이 없어요</h1>
          <Link to="/history" className="btn btn--ghost">
            지난 방송 보기
          </Link>
        </div>
      </div>
    )
  }

  const { briefing } = data
  const isCurrent = player.briefing?.date === date
  // 지금 재생 중인 구간 = 시작 시간이 현재 시간보다 작거나 같은 마지막 구간
  const activeIdx = isCurrent ? segments.findLastIndex((s) => s.start <= player.currentTime) : -1
  const { year, month, day, weekday } = dateParts(date)

  const playFrom = (sec) => {
    player.load(briefing)
    player.seek(sec)
    player.play()
  }
  const visible = segments.map((s, i) => ({ ...s, i })).filter((s) => filter === '전체' || s.category === filter)

  return (
    <div className="container page script">
      <aside className="script__side">
        <Link to="/" className="script__back">
          <Icon name="chevronLeft" size={18} /> 오늘의 브리핑
        </Link>
        <p className="text-secondary caption">
          {year}.{String(month).padStart(2, '0')}.{String(day).padStart(2, '0')} ({weekday}) 06:00 방송
        </p>
        <h1 className="script__title">{briefing.title}</h1>

        <div className="filters" role="group" aria-label="카테고리 필터">
          {categories.map((c) => (
            <button
              key={c}
              type="button"
              className={`filter${filter === c ? ' is-active' : ''}`}
              aria-pressed={filter === c}
              onClick={() => setFilter(c)}
            >
              {c}
            </button>
          ))}
        </div>

        <hr className="divider only-desktop-block" />
        <p className="caption text-secondary only-desktop-block">목차</p>
        <ol className="toc only-desktop-block">
          {segments.map((s, i) => (
            <li key={s.start}>
              <button type="button" className={`toc__item${i === activeIdx ? ' is-active' : ''}`} onClick={() => playFrom(s.start)}>
                <span className="toc__time">{formatClock(s.start)}</span>
                <span>{s.title}</span>
              </button>
            </li>
          ))}
        </ol>
      </aside>

      <div className="script__body">
        {visible.map((s) => {
          const active = s.i === activeIdx
          return (
            <article key={s.start} className={`segment${active ? ' is-active' : ''}`} aria-current={active ? 'true' : undefined}>
              <div className="segment__meta">
                <button type="button" className="segment__time" onClick={() => playFrom(s.start)} aria-label={`${formatClock(s.start)}부터 듣기`}>
                  {formatClock(s.start)}
                </button>
                <CategoryChip label={s.category} />
                {active && <span className="segment__now">▶ 재생 중</span>}
              </div>
              <p className="segment__text">{s.text}</p>
            </article>
          )
        })}
      </div>
    </div>
  )
}
