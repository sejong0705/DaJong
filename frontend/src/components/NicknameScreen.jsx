// 닉네임 입력 화면
// - 처음 접속: 닉네임을 정해야 앱으로 들어가요
// - 닉네임 변경: 상단의 닉네임을 누르면 열리고, '취소'로 닫을 수 있어요
import { useEffect, useRef, useState } from 'react'
import Logo from './Logo'
import { cleanNickname, NICKNAME_MAX } from '../api/user'
import { useUser } from '../context/UserContext'
import './NicknameScreen.css'

export default function NicknameScreen({ onClose }) {
  const { user, setNickname } = useUser()
  const editing = Boolean(user)
  const [value, setValue] = useState(user?.nickname ?? '')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // 변경 화면은 Esc 로 닫기
  useEffect(() => {
    if (!onClose) return
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const name = cleanNickname(value)
  const valid = name.length >= 1 && name.length <= NICKNAME_MAX

  const onSubmit = async (e) => {
    e.preventDefault()
    if (!valid || saving) return
    setSaving(true)
    setError(null)
    try {
      await setNickname(name)
      onClose?.()
    } catch (err) {
      setError(err.message || '저장하지 못했어요. 잠시 후 다시 시도해 주세요.')
      setSaving(false)
    }
  }

  return (
    <div className="nickname" role="dialog" aria-modal="true" aria-labelledby="nickname-title">
      <div className="nickname__glow" />
      <form className="nickname__card" onSubmit={onSubmit}>
        <Logo variant="symbol" size={64} />
        <h1 id="nickname-title" className="nickname__title">
          {editing ? '닉네임 바꾸기' : '반가워요!'}
        </h1>
        <p className="nickname__desc">
          {editing ? (
            '새로운 닉네임을 입력해 주세요.'
          ) : (
            <>
              던에어에서 부를 닉네임을 알려 주세요.
              <br />
              다음부터는 바로 들어올 수 있어요.
            </>
          )}
        </p>

        <label className="visually-hidden" htmlFor="nickname-input">
          닉네임
        </label>
        <input
          id="nickname-input"
          ref={inputRef}
          className="nickname__input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          maxLength={NICKNAME_MAX + 10} // 공백 정리 전 여유. 실제 제한은 정리 후 20자
          placeholder="예: 출근길 세종"
          autoComplete="nickname"
          enterKeyHint="done"
        />
        <p className={`nickname__hint${name.length > NICKNAME_MAX ? ' is-error' : ''}`}>
          {name.length}/{NICKNAME_MAX}
        </p>
        {error && (
          <p className="nickname__error" role="alert">
            {error}
          </p>
        )}

        <div className="nickname__actions">
          {onClose && (
            <button type="button" className="btn btn--ghost" onClick={onClose}>
              취소
            </button>
          )}
          <button type="submit" className="btn btn--primary" disabled={!valid || saving}>
            {saving ? '저장 중…' : editing ? '바꾸기' : '시작하기'}
          </button>
        </div>
      </form>
    </div>
  )
}
