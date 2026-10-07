// 03 지난 방송 (캘린더 + 목록)
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon from '../components/Icon'
import { EpisodeItem } from '../components/BriefingItems'
import { listBriefings } from '../api/briefing'
import { useAsync } from '../hooks/useAsync'
import { usePlayer } from '../context/PlayerContext'
import { todayKey } from '../utils/date'
import './pages.css'

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

function shiftMonth(month, n) {
  const [y, m] = month.split('-').map(Number)
  const d = new Date(Date.UTC(y, m - 1 + n, 1))
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`
}

export default function HistoryPage() {
  const today = todayKey()
  const thisMonth = today.slice(0, 7)
  const [month, setMonth] = useState(thisMonth)
  const { data, loading } = useAsync(() => listBriefings(month), [month])
  const navigate = useNavigate()
  const player = usePlayer()

  const list = useMemo(() => [...(data ?? [])].sort((a, b) => (a.date < b.date ? 1 : -1)), [data])
  const dates = useMemo(() => new Set(list.map((b) => b.date)), [list])

  // 달력 칸 만들기 (앞쪽 빈칸 + 1일~말일)
  const [y, m] = month.split('-').map(Number)
  const firstWeekday = new Date(Date.UTC(y, m - 1, 1)).getUTCDay()
  const lastDay = new Date(Date.UTC(y, m, 0)).getUTCDate()
  const cells = [...Array(firstWeekday).fill(null), ...Array.from({ length: lastDay }, (_, i) => i + 1)]

  return (
    <div className="container page history">
      <header className="page-header">
        <h1 className="display-xl">지난 방송</h1>
        <p className="text-secondary">매일 아침 6시, 새 방송이 쌓여요. 날짜를 선택해 다시 들어보세요.</p>
      </header>

      <div className="history__layout">
        <section className="card calendar" aria-label={`${y}년 ${m}월 달력`}>
          <div className="calendar__nav">
            <button type="button" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="이전 달">
              <Icon name="chevronLeft" size={20} />
            </button>
            <h2>
              {y}년 {m}월
            </h2>
            <button type="button" onClick={() => setMonth(shiftMonth(month, 1))} disabled={month >= thisMonth} aria-label="다음 달">
              <Icon name="chevronRight" size={20} />
            </button>
          </div>
          <div className="calendar__grid">
            {WEEKDAYS.map((w) => (
              <span key={w} className="calendar__weekday">
                {w}
              </span>
            ))}
            {cells.map((d, i) => {
              if (!d) return <span key={`e${i}`} />
              const key = `${month}-${String(d).padStart(2, '0')}`
              const has = dates.has(key)
              return (
                <button
                  key={key}
                  type="button"
                  className={`calendar__day${key === today ? ' is-today' : ''}${has ? ' has-episode' : ''}`}
                  disabled={!has}
                  onClick={() => navigate(`/script/${key}`)}
                  aria-label={`${m}월 ${d}일${has ? ' 방송 보기' : ' 방송 없음'}`}
                >
                  {d}
                  <i />
                </button>
              )
            })}
          </div>
          <p className="calendar__legend">
            <i /> 방송이 있는 날
          </p>
        </section>

        <section className="history__list">
          <div className="section-header">
            <h2>
              {m}월 방송 · {list.length}개
            </h2>
            <span className="caption text-secondary">최신순</span>
          </div>
          {loading ? (
            <p className="text-secondary">불러오는 중…</p>
          ) : list.length === 0 ? (
            <p className="text-secondary">이 달에는 방송이 없어요.</p>
          ) : (
            <ul className="episode-list">
              {list.map((b) => (
                <EpisodeItem key={b.date} briefing={b} onPlay={(x) => player.load(x, { autoplay: true })} />
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}
