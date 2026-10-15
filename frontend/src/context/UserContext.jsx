import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { fetchUser, getCachedUser, getDeviceId, registerUser, setCachedUser } from '../api/user'

/**
 * 이 기기의 사용자(닉네임)를 앱 전체에서 공유해요.
 *
 * - 한 번 닉네임을 정하면 다음부터는 바로 들어가요 (자동 로그인)
 * - 저장해 둔 사용자로 먼저 화면을 그리고, 뒤에서 서버에 한 번 확인해요
 *   · 서버에서 지워진 기기(404)면 닉네임을 다시 받아요
 *   · 인터넷이 안 되는 등 확인에 실패하면 저장해 둔 값으로 계속 써요
 */
const UserContext = createContext(null)

export function UserProvider({ children }) {
  const [user, setUser] = useState(getCachedUser)

  const save = useCallback((u) => {
    setCachedUser(u)
    setUser(u)
  }, [])

  // 앱을 열 때 한 번 서버 확인 (마지막 접속 시간도 이때 갱신돼요)
  useEffect(() => {
    if (!getCachedUser()) return
    let alive = true
    fetchUser()
      .then((u) => alive && save(u))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [save])

  /** 닉네임 등록 / 변경. 실패하면 에러를 던져요 (화면에서 메시지 표시) */
  const setNickname = useCallback(async (nickname) => save(await registerUser(nickname)), [save])

  const value = useMemo(() => ({ user, deviceId: getDeviceId(), setNickname }), [user, setNickname])

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>
}

export function useUser() {
  const ctx = useContext(UserContext)
  if (!ctx) throw new Error('useUser 는 UserProvider 안에서만 쓸 수 있어요')
  return ctx
}
