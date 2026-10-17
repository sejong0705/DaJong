// 첫 접속 닉네임 입력 화면 — 닉네임을 정해야 앱으로 들어가요
// (닉네임 수정은 상단 'OO님' 버튼의 NicknameEditDialog)
import { useEffect, useRef, useState } from 'react'
import Logo from './Logo'
import { cleanNickname, NICKNAME_MAX } from '../api/user'
import { useUser } from '../context/UserContext'
import './NicknameScreen.css'

export default function NicknameScreen() {
  const { setNickname } = useUser()
  const [value, setValue] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const name = cleanNickname(value)
  const valid = name.length >= 1 && name.length <= NICKNAME_MAX

  const onSubmit = async (e) => {
    e.preventDefault()
    if (!valid || saving) return
    setSaving(true)
    setError(null)
    try {
      await setNickname(name)
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
          반가워요!
        </h1>
        <p className="nickname__desc">
          던에어에서 부를 닉네임을 알려 주세요.
          <br />
          다음부터는 바로 들어올 수 있어요.
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
          <button type="submit" className="btn btn--primary" disabled={!valid || saving}>
            {saving ? '저장 중…' : '시작하기'}
          </button>
        </div>
      </form>
    </div>
  )
}
