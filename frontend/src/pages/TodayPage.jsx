// 01 홈 - 오늘의 브리핑 (+ 04 방송 준비 중, 05 로딩)
import { Link } from 'react-router-dom'
import Icon from '../components/Icon'
import SplashScreen from '../components/SplashScreen'
import { CategoryChip, EpisodeItem, HeadlineItem } from '../components/BriefingItems'
import { getBriefing, listBriefings } from '../api/briefing'
import { useAsync } from '../hooks/useAsync'
import { usePlayer } from '../context/PlayerContext'
import { addDays, currentHourKST, formatDuration, todayKey } from '../utils/date'
import './pages.css'

export default function TodayPage() {
  const today = todayKey()
  const { data: briefing, loading, error } = useAsync(() => getBriefing(today), [today])
  const recent = useAsync(async () => {
    // 월초에도 지난 방송이 보이도록 이번 달 + 지난달을 합쳐요
    const prevMonth = addDays(`${today.slice(0, 7)}-01`, -1).slice(0, 7)
    const [a, b] = await Promise.all([listBriefings(today.slice(0, 7)), listBriefings(prevMonth)])
    return [...a, ...b].filter((x) => x.date !== today).sort((x, y) => (x.date < y.date ? 1 : -1))
  }, [today])
  const player = usePlayer()

  if (loading) return <SplashScreen />
  if (error) return <ErrorState message={error.message} />
  if (!briefing) return <PreparingState yesterday={recent.data?.[0]} />

  const isCurrent = player.briefing?.date === briefing.date
  const playing = isCurrent && player.isPlaying

  const onHero = () => (isCurrent ? player.toggle() : player.load(briefing, { autoplay: true }))
  const onHeadline = (time) => {
    player.load(briefing)
    player.seek(time)
    player.play()
  }
  const w = briefing.weather

  return (
    <div className="container page today">
      <div className="today__top">
        <section className="hero" aria-labelledby="hero-title">
          <span className="hero__badge">
            <i /> ON AIR · 06:00 업데이트
          </span>
          <h1 id="hero-title" className="hero__title">
            {briefing.title}
          </h1>
          <p className="hero__meta">
            {formatDuration(briefing.duration)}
            {briefing.categories?.length ? ` · ${briefing.categories.join(' · ')}` : ''}
          </p>
          <button type="button" className="hero__play" onClick={onHero}>
            <span className="hero__play-icon">
              <Icon name={playing ? 'pause' : 'play'} size={28} />
            </span>
            {playing ? '일시정지' : isCurrent ? '이어 듣기' : '오늘 브리핑 듣기'}
          </button>
        </section>

        {w && (
          <section className="card weather" aria-label="오늘의 날씨">
            <p className="weather__label">오늘의 날씨 · {w.region}</p>
            <div className="weather__row">
              <span className="weather__icon">
                <Icon name="sun" size={30} />
              </span>
              <div>
                <p className="weather__temp">
                  {w.min}° / {w.max}°
                </p>
                <p className="text-secondary weather__sky">{w.sky}</p>
              </div>
            </div>
            <p className="weather__rain">
              <Icon name="umbrella" size={18} /> 강수 확률 {w.rainProb}%
            </p>
            <hr className="divider" />
            <div className="weather__tip">
              <p className="weather__tip-label">
                <Icon name="shirt" size={18} /> 옷차림 추천
              </p>
              <p>{briefing.weatherSummary}</p>
            </div>
          </section>
        )}
      </div>

      <div className="today__bottom">
        <section className="today__headlines">
          <div className="section-header">
            <h2>오늘의 헤드라인</h2>
            <Link to={`/script/${briefing.date}`} className="link-accent">
              대본 전문 보기 ›
            </Link>
          </div>
          <ul className="card headline-list">
            {briefing.headlines.map((h) => (
              <HeadlineItem key={h.time} {...h} onSelect={onHeadline} />
            ))}
          </ul>
        </section>

        <section className="today__recent">
          <div className="section-header">
            <h2>지난 방송</h2>
            <Link to="/history" className="link-accent">
              더보기 ›
            </Link>
          </div>
          <ul className="episode-list">
            {(recent.data ?? []).slice(0, 3).map((b) => (
              <EpisodeItem key={b.date} briefing={b} onPlay={(x) => player.load(x, { autoplay: true })} />
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}

/** 04 방송 준비 중 (오전 6시 이전) */
function PreparingState({ yesterday }) {
  const player = usePlayer()
  const minutesLeft = Math.max(0, (6 - currentHourKST()) * 60 - new Date().getMinutes())
  return (
    <div className="container page">
      <div className="card empty-state">
        <div className="empty-state__art">
          <Icon name="sun" size={56} />
        </div>
        <h1>오늘 방송을 준비하고 있어요</h1>
        <p className="text-secondary">
          매일 아침 6시에 새 브리핑이 올라와요.
          <br />
          그동안 어제 방송을 먼저 들어보시겠어요?
        </p>
        {minutesLeft > 0 && <CategoryChip label={`방송까지 ${minutesLeft}분`} />}
        <div className="empty-state__actions">
          {yesterday && (
            <button type="button" className="btn btn--primary" onClick={() => player.load(yesterday, { autoplay: true })}>
              어제 방송 듣기
            </button>
          )}
          <Link to="/history" className="btn btn--ghost">
            지난 방송 보기
          </Link>
        </div>
      </div>
    </div>
  )
}

function ErrorState({ message }) {
  return (
    <div className="container page">
      <div className="card empty-state">
        <h1>방송 정보를 불러오지 못했어요</h1>
        <p className="text-secondary">{message}</p>
        <button type="button" className="btn btn--primary" onClick={() => window.location.reload()}>
          다시 시도
        </button>
      </div>
    </div>
  )
}
