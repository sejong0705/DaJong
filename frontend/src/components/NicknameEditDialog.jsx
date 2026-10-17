// 닉네임 수정 팝업 (상단 'OO님' 버튼을 누르면 열려요)
// - 데스크톱: 화면 가운데 카드 / 모바일: 아래에서 올라오는 시트
// - 상단 메뉴(backdrop-filter) 안에서 열면 position:fixed 가 메뉴 영역에 갇혀서, body 에 바로 붙여요(portal)
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from './Icon'
import { cleanNickname, NICKNAME_MAX } from '../api/user'
import { useUser } from '../context/UserContext'
import './NicknameEditDialog.css'

export default function NicknameEditDialog({ onClose }) {
  const { user, setNickname } = useUser()
  const current = user?.nickname ?? ''
  const [value, setValue] = useState(current)
  const [error, setError] = useState(null)
  const [status, setStatus] = useState('idle') // idle | saving | done
  const inputRef = useRef(null)

  const name = cleanNickname(value)
  const tooLong = name.length > NICKNAME_MAX
  const changed = name !== current
  const canSave = name.length >= 1 && !tooLong && changed && status === 'idle'

  // 열릴 때: 입력창 포커스(전체 선택), 뒤 페이지 스크롤 잠금, Esc 로 닫기
  useEffect(() => {
    inputRef.current?.select()
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prevOverflow
      window.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  const onSubmit = async (e) => {
    e.preventDefault()
    if (!canSave) return
    setStatus('saving')
    setError(null)
    try {
      await setNickname(name)
      setStatus('done')
      setTimeout(onClose, 700) // '수정 완료!' 를 잠깐 보여주고 닫기
    } catch (err) {
      setError(err.message || '저장하지 못했어요. 잠시 후 다시 시도해 주세요.')
      setStatus('idle')
    }
  }

  return createPortal(
    <div className="nick-dialog" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="nick-dialog__panel" onSubmit={onSubmit} role="dialog" aria-modal="true" aria-labelledby="nick-dialog-title">
        <span className="nick-dialog__handle" aria-hidden="true" />
        <button type="button" className="nick-dialog__close" onClick={onClose} aria-label="닫기">
          <Icon name="close" size={20} />
        </button>

        <div className="nick-dialog__avatar" aria-hidden="true">
          {(name || current).slice(0, 1)}
        </div>
        <h2 id="nick-dialog-title" className="nick-dialog__title">
          닉네임 수정
        </h2>
        <p className="nick-dialog__desc">
          지금은 <b>{current}</b>님으로 불러드리고 있어요
        </p>

        <div className={`nick-dialog__field${error || tooLong ? ' is-error' : ''}`}>
          <Icon name="edit" size={18} className="nick-dialog__field-icon" />
          <label className="visually-hidden" htmlFor="nick-dialog-input">
            새 닉네임
          </label>
          <input
            id="nick-dialog-input"
            ref={inputRef}
            value={value}
            onChange={(e) => {
              setValue(e.target.value)
              setError(null)
            }}
            maxLength={NICKNAME_MAX + 10}
            placeholder="새 닉네임"
            autoComplete="nickname"
            enterKeyHint="done"
            disabled={status !== 'idle'}
          />
          {value && status === 'idle' && (
            <button
              type="button"
              className="nick-dialog__clear"
              onClick={() => {
                setValue('')
                inputRef.current?.focus()
              }}
              aria-label="지우기"
            >
              <Icon name="close" size={14} strokeWidth={2.4} />
            </button>
          )}
        </div>
        <div className="nick-dialog__meta">
          <span className="nick-dialog__error" role="alert">
            {error || (tooLong ? `${NICKNAME_MAX}자까지 쓸 수 있어요` : '')}
          </span>
          <span className={tooLong ? 'is-error' : ''}>
            {name.length}/{NICKNAME_MAX}
          </span>
        </div>

        {/* 방송에서 어떻게 들리는지 미리 보기 */}
        <div className="nick-dialog__preview">
          <span className="nick-dialog__preview-label">방송에서는 이렇게 인사해요</span>
          <p>
            “안녕하세요, <b>{name || '○○'}</b>님.”
          </p>
        </div>

        <div className="nick-dialog__actions">
          <button type="button" className="nick-dialog__btn nick-dialog__btn--ghost" onClick={onClose} disabled={status === 'saving'}>
            취소
          </button>
          <button
            type="submit"
            className={`nick-dialog__btn nick-dialog__btn--primary${status === 'done' ? ' is-done' : ''}`}
            disabled={!canSave && status !== 'done'}
          >
            {status === 'done' ? (
              <>
                <Icon name="check" size={18} strokeWidth={2.4} /> 수정 완료!
              </>
            ) : status === 'saving' ? (
              '저장 중…'
            ) : (
              '수정 완료'
            )}
          </button>
        </div>
      </form>
    </div>,
    document.body,
  )
}
