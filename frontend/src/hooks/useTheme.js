import { useCallback, useEffect, useState } from 'react'

const KEY = 'dawnair-theme'
const media = () => window.matchMedia('(prefers-color-scheme: dark)')

function readSaved() {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null // 사생활 보호 모드 등에서는 저장소를 못 쓸 수 있어요
  }
}

/**
 * 라이트/다크 테마
 * - 사용자가 고른 적 없으면 OS 설정을 따라가요
 * - 고르면 <html data-theme="..."> 로 고정하고 기억해요
 */
export function useTheme() {
  const [saved, setSaved] = useState(readSaved)
  const [systemDark, setSystemDark] = useState(() => media().matches)

  useEffect(() => {
    const m = media()
    const onChange = (e) => setSystemDark(e.matches)
    m.addEventListener('change', onChange)
    return () => m.removeEventListener('change', onChange)
  }, [])

  const theme = saved ?? (systemDark ? 'dark' : 'light')

  useEffect(() => {
    const root = document.documentElement
    if (saved) root.dataset.theme = saved
    else delete root.dataset.theme
  }, [saved])

  const toggle = useCallback(() => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setSaved(next)
    try {
      localStorage.setItem(KEY, next)
    } catch {
      /* 저장 실패해도 화면 전환은 그대로 동작 */
    }
  }, [theme])

  return { theme, toggle }
}
