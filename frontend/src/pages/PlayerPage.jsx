// 06 방송 화면 (재생) — 하단 재생바를 누르면 열려요
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Icon from '../components/Icon'
import Logo from '../components/Logo'
import BroadcastOrb from '../components/BroadcastOrb'
import { getBriefing } from '../api/briefing'
import { usePlayer } from '../context/PlayerContext'
import { currentHourKST, dateParts, formatClock, formatDuration, formatLongDate, formatRate, todayKey } from '../utils/date'
import './PlayerPage.css'

function greeting() {
  const h = currentHourKST()
  if (h < 12) return '좋은 아침이에요.'
  if (h < 18) return '오늘 아침 소식, 다시 들어볼까요?'
  return '오늘 하루 수고 많았어요.'
}

export default function PlayerPage() {
  const player = usePlayer()
  const { briefing, isPlaying, currentTime, duration, rate } = player
  const navigate = useNavigate()
  const [showChapters, setShowChapters] = useState(false)
  const [missing, setMissing] = useState(false)

  // 주소로 바로 들어온 경우: 오늘 방송을 플레이어에 올려둠 (자동 재생은 안 함)
  useEffect(() => {
    if (briefing) return
    getBriefing(todayKey()).then((b) => (b ? player.load(b) : setMissing(true)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [briefing])

  const chapters = useMemo(() => {
    if (!briefing) return []
    const list = [{ time: 0, title: '오프닝' }, ...briefing.headlines.filter((h) => h.time > 0)]
    return list
  }, [briefing])

  const close = () => (window.history.state?.idx > 0 ? navigate(-1) : navigate('/'))

  if (!briefing) {
    return (
      <div className="player-page">
        <div className="player-page__empty">
          <p>{missing ? '아직 오늘 방송이 없어요.' : '방송을 불러오는 중…'}</p>
          <Link to="/" className="btn btn--ghost">
            홈으로
          </Link>
        </div>
      </div>
    )
  }

  const total = duration || briefing.duration || 0
  const current = chapters.findLastIndex((c) => c.time <= currentTime)
  const { month, day } = dateParts(briefing.date)
  const w = briefing.weather

  const prevChapter = () => {
    const c = chapters[current]
    // 챕터 시작 3초 이후면 그 챕터 처음으로, 아니면 이전 챕터로
    if (c && currentTime - c.time > 3) player.seek(c.time)
    else player.seek(chapters[Math.max(0, current - 1)]?.time ?? 0)
  }
  const nextChapter = () => {
    const n = chapters[current + 1]
    if (n) player.seek(n.time)
  }
  const goChapter = (t) => {
    player.seek(t)
    if (!isPlaying) player.play()
  }

  return (
    <div className="player-page">
      <span className="player-page__handle only-mobile-block" aria-hidden="true" />
      <header className="player-page__header container">
        <Link to="/" aria-label="DawnAir 홈">
          <Logo />
        </Link>
        <div className="player-page__header-actions">
          <Link to="/history" aria-label="지난 방송">
            <Icon name="history" size={24} />
          </Link>
          <button type="button" className="player-page__close" onClick={close} aria-label="접기">
            <Icon name="chevronDown" size={18} />
            <span>접기</span>
          </button>
        </div>
      </header>

      <div className="player-page__body container">
        <section className="now-playing" aria-label="지금 재생 중">
          <BroadcastOrb />

          <h1 className="now-playing__greeting">{greeting()}</h1>
          <p className="now-playing__muted">
            {formatLongDate(briefing.date)}
            {w ? ` · ${w.region} ${w.min}°~${w.max}°` : ''}
          </p>

          <p className="now-playing__episode">
            {String(day).padStart(2, '0')} · {month}월 {day}일 아침
          </p>
          <p className="now-playing__muted">
            {formatDuration(total)} · 날씨와 {briefing.headlines.filter((h) => h.category !== '날씨').length}개 소식
          </p>

          <div className="controls">
            <button type="button" onClick={prevChapter} aria-label="이전 챕터">
              <Icon name="prev" size={26} />
            </button>
            <button type="button" className="controls__skip" onClick={() => player.skip(-15)} aria-label="15초 뒤로">
              <Icon name="rewind" size={36} />
              <span>15</span>
            </button>
            <button type="button" className="controls__play" onClick={player.toggle} aria-label={isPlaying ? '일시정지' : '재생'}>
              <Icon name={isPlaying ? 'pause' : 'play'} size={32} />
            </button>
            <button type="button" className="controls__skip" onClick={() => player.skip(15)} aria-label="15초 앞으로">
              <Icon name="forward" size={36} />
              <span>15</span>
            </button>
            <button type="button" onClick={nextChapter} disabled={current >= chapters.length - 1} aria-label="다음 챕터">
              <Icon name="next" size={26} />
            </button>
          </div>

          <ChapterProgress chapters={chapters} total={total} currentTime={currentTime} onSeek={player.seek} />
          <div className="now-playing__times">
            <span>{formatClock(currentTime)}</span>
            <span>{formatClock(total)}</span>
          </div>

          {player.error && <p className="now-playing__error">{player.error}</p>}

          <div className="now-playing__bottom">
            <button type="button" onClick={player.cycleRate}>
              {formatRate(rate)}
            </button>
            <button type="button" className="only-mobile-flex" onClick={() => setShowChapters((v) => !v)} aria-expanded={showChapters}>
              <Icon name="chapters" size={20} /> 목차 {chapters.length}
            </button>
          </div>
        </section>

        {/* 목차 카드 + 위에 대본 링크 (모바일에서는 '목차' 버튼을 눌렀을 때만 보여요) */}
        <div className={`chapter-column${showChapters ? ' is-open' : ''}`}>
          <Link to={`/script/${briefing.date}`} className="script-link">
            <span className="script-link__icon">
              <Icon name="script" size={18} />
            </span>
            <span className="script-link__label">대본 읽으러 가기</span>
            <Icon name="chevronRight" size={20} />
          </Link>

          <section className="chapters" aria-label="목차">
            <div className="chapters__header">
              <h2>목차</h2>
              <span>{chapters.length}개 챕터</span>
            </div>
            <ol>
              {chapters.map((c, i) => (
                <li key={c.time}>
                  <button type="button" className={`chapters__item${i === current ? ' is-active' : ''}`} onClick={() => goChapter(c.time)}>
                    <span className="chapters__time">{formatClock(c.time)}</span>
                    <span className="chapters__title">{c.title}</span>
                    {i === current && <span className="chapters__now">재생 중</span>}
                  </button>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>
    </div>
  )
}

/** 챕터별로 나뉜 진행바 */
function ChapterProgress({ chapters, total, currentTime, onSeek }) {
  if (!total) return <div className="chapter-progress" />
  // 음원이 목차보다 짧을 수 있어서, 음원 길이 안에 있는 챕터만 그리고 끝은 음원 길이에서 잘라요
  const inRange = chapters.filter((c, i) => i === 0 || c.time < total)
  const parts = inRange.map((c, i) => {
    const end = Math.min(inRange[i + 1]?.time ?? total, total)
    const len = Math.max(0, end - c.time)
    const played = Math.min(len, Math.max(0, currentTime - c.time))
    return { start: c.time, len, ratio: len ? played / len : 0 }
  })

  // 구간 사이에 4px 틈(CSS gap)이 있어서, 손잡이 위치도 틈을 빼고 계산해야 채워진 막대 끝과 맞아요
  const GAP = 4
  const idx = Math.max(0, parts.findLastIndex((p) => p.start <= currentTime))
  const knobRatio = Math.min(1, Math.max(0, currentTime / total))
  const knobLeft = `calc(${knobRatio} * (100% - ${GAP * (parts.length - 1)}px) + ${GAP * idx}px)`

  // 누른 구간 안에서의 위치로 시간 계산 (틈을 누르면 전체 비율로)
  const onClick = (e) => {
    const seg = e.target.closest('.chapter-progress__seg')
    if (seg) {
      const p = parts[Number(seg.dataset.index)]
      const rect = seg.getBoundingClientRect()
      onSeek(p.start + ((e.clientX - rect.left) / rect.width) * p.len)
      return
    }
    const rect = e.currentTarget.getBoundingClientRect()
    onSeek(((e.clientX - rect.left) / rect.width) * total)
  }

  return (
    <div
      className="chapter-progress"
      onClick={onClick}
      role="slider"
      aria-label="재생 위치"
      aria-valuemin={0}
      aria-valuemax={Math.round(total)}
      aria-valuenow={Math.round(currentTime)}
      aria-valuetext={formatClock(currentTime)}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'ArrowRight') onSeek(currentTime + 5)
        if (e.key === 'ArrowLeft') onSeek(currentTime - 5)
      }}
    >
      {parts.map((p, i) => (
        <span key={p.start} className="chapter-progress__seg" data-index={i} style={{ flexGrow: p.len }}>
          <span style={{ width: `${p.ratio * 100}%` }} />
        </span>
      ))}
      <span className="chapter-progress__knob" style={{ left: knobLeft }} />
    </div>
  )
}
