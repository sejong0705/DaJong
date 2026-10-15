// 사용자 (기기별 닉네임)
//
// 백엔드: user Lambda (함수 URL)
//   POST {URL}  body { deviceId, nickname }  → { user }   등록 / 닉네임 변경
//   GET  {URL}?deviceId=...                  → { user }   조회 (없으면 404)
//
// 비밀번호 없이 브라우저(기기)마다 만든 UUID 를 사용자 ID 로 써요.
// 브라우저 데이터를 지우거나 기기를 바꾸면 새 사용자로 등록됩니다 (의도된 동작).
// .env 의 VITE_USER_API_URL 이 비어 있으면 서버 없이 이 브라우저에만 저장해요 (목업).

const API_URL = (import.meta.env.VITE_USER_API_URL || '').replace(/\/$/, '')
export const isUserMock = !API_URL

const DEVICE_KEY = 'dawnair-device-id'
const USER_KEY = 'dawnair-user'
export const NICKNAME_MAX = 20 // 백엔드와 같은 기준

// ---------------------------------------------------------------- 브라우저 저장소
// 사생활 보호 모드 등에서는 저장소를 못 쓸 수 있어서 모두 try/catch

function read(key) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key, value) {
  try {
    if (value == null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    /* 저장 실패해도 이번 접속 동안은 메모리 값으로 동작 */
  }
}

function uuid() {
  if (crypto.randomUUID) return crypto.randomUUID()
  // randomUUID 가 없는 오래된 브라우저 (http 접속 등)
  const b = crypto.getRandomValues(new Uint8Array(16))
  b[6] = (b[6] & 0x0f) | 0x40
  b[8] = (b[8] & 0x3f) | 0x80
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('')
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`
}

/** 이 기기의 ID. 처음이면 새로 만들어 저장 */
export function getDeviceId() {
  let id = read(DEVICE_KEY)
  if (!id) {
    id = uuid()
    write(DEVICE_KEY, id)
  }
  return id
}

/** 마지막으로 확인된 사용자 (서버 응답을 기다리지 않고 바로 화면을 그리기 위해) */
export function getCachedUser() {
  try {
    const u = JSON.parse(read(USER_KEY))
    return u?.deviceId === getDeviceId() && u.nickname ? u : null
  } catch {
    return null
  }
}

export function setCachedUser(user) {
  write(USER_KEY, user ? JSON.stringify(user) : null)
}

/** 입력값 정리: 앞뒤 공백 · 제어문자 제거 */
export function cleanNickname(v = '') {
  return v.replace(/[\x00-\x1f\x7f]/g, '').trim()
}

// ---------------------------------------------------------------- 서버 호출
async function request(url, options) {
  const res = await fetch(url, options)
  const body = await res.json().catch(() => ({}))
  if (res.status === 404) return null
  if (!res.ok) throw new Error(body.error || `요청 실패 (${res.status})`)
  return body.user
}

/** 서버에 등록된 사용자. 등록 안 된 기기면 null */
export async function fetchUser(deviceId = getDeviceId()) {
  if (isUserMock) return getCachedUser()
  return request(`${API_URL}/?deviceId=${encodeURIComponent(deviceId)}`)
}

/** 닉네임 등록 / 변경 */
export async function registerUser(nickname, deviceId = getDeviceId()) {
  const name = cleanNickname(nickname)
  if (!name || name.length > NICKNAME_MAX) throw new Error(`닉네임은 1~${NICKNAME_MAX}자로 입력해 주세요.`)
  if (isUserMock) {
    const t = new Date().toISOString()
    return { deviceId, nickname: name, createdAt: getCachedUser()?.createdAt ?? t, updatedAt: t, lastSeenAt: t }
  }
  return request(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ deviceId, nickname: name }),
  })
}
