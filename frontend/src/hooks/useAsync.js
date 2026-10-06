import { useEffect, useState } from 'react'

/** 비동기 함수를 호출하고 { data, loading, error } 를 돌려주는 간단한 훅 */
export function useAsync(fn, deps) {
  const [state, setState] = useState({ data: undefined, loading: true, error: null })

  useEffect(() => {
    let alive = true
    setState((s) => ({ ...s, loading: true, error: null }))
    fn()
      .then((data) => alive && setState({ data, loading: false, error: null }))
      .catch((error) => alive && setState({ data: undefined, loading: false, error }))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return state
}
