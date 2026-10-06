// 날짜 · 시간 유틸 (모든 날짜는 한국 시간 기준)

const KST = 'Asia/Seoul'

/** 한국 시간 기준 'YYYY-MM-DD' */
export function toDateKey(date = new Date()) {
  // en-CA 로케일은 YYYY-MM-DD 형식으로 나와요
  return new Intl.DateTimeFormat('en-CA', { timeZone: KST }).format(date)
}

export function todayKey() {
  return toDateKey(new Date())
}

/** 한국 시간 기준 현재 시(0~23) */
export function currentHourKST() {
  return Number(
    new Intl.DateTimeFormat('en-US', { timeZone: KST, hour: 'numeric', hourCycle: 'h23' }).format(new Date()),
  )
}

/** 'YYYY-MM-DD' → Date (정오로 잡아서 시간대 경계 문제 방지) */
export function fromDateKey(key) {
  const [y, m, d] = key.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d, 3))
}

/** 날짜 키에서 n일 더하기/빼기 */
export function addDays(key, n) {
  const d = fromDateKey(key)
  d.setUTCDate(d.getUTCDate() + n)
  return toDateKey(d)
}

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

/** '2026-10-06' → { month: 10, day: 6, weekday: '화' } */
export function dateParts(key) {
  const d = fromDateKey(key)
  return { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1, day: d.getUTCDate(), weekday: WEEKDAYS[d.getUTCDay()] }
}

/** '10월 6일 화요일' */
export function formatLongDate(key) {
  const { month, day, weekday } = dateParts(key)
  return `${month}월 ${day}일 ${weekday}요일`
}

/** 초 → '12:40' */
export function formatClock(sec = 0) {
  const s = Math.max(0, Math.floor(sec))
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

/** 초 → '12분 40초' */
export function formatDuration(sec = 0) {
  const s = Math.round(sec)
  return `${Math.floor(s / 60)}분 ${s % 60}초`
}
