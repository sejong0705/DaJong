import { useCallback, useRef } from 'react'

/**
 * <audio> 요소의 실시간 볼륨을 읽는 훅 (Web Audio API · AnalyserNode)
 *
 * 사용법
 *   const { connect, getLevel } = useAudioAnalyser(audioElement)
 *   connect()     // 재생 버튼을 누를 때 호출 (브라우저 정책상 사용자 동작 안에서 시작해야 함)
 *   getLevel()    // 0 ~ 1 사이 볼륨 값. requestAnimationFrame 안에서 매 프레임 읽기
 *
 * ⚠️ 중요: 오디오가 다른 도메인(CloudFront 등)에 있으면
 *   - <audio crossOrigin="anonymous"> 로 불러와야 하고
 *   - S3/CloudFront 응답에 CORS 헤더(Access-Control-Allow-Origin)가 있어야 해요.
 *   CORS 가 없으면 createMediaElementSource 를 거친 소리가 "무음"이 됩니다.
 */
export function useAudioAnalyser(audio) {
  const ctxRef = useRef(null)
  const analyserRef = useRef(null)
  const bufRef = useRef(null)

  const connect = useCallback(() => {
    if (!audio) return
    if (ctxRef.current) {
      // 이미 연결됨 → 일시정지 상태였다면 다시 깨우기
      if (ctxRef.current.state === 'suspended') ctxRef.current.resume()
      return
    }
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return

    const ctx = new Ctx()
    // 한 <audio> 요소에 MediaElementSource 는 딱 한 번만 만들 수 있어요
    const source = ctx.createMediaElementSource(audio)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 512
    analyser.smoothingTimeConstant = 0.8

    source.connect(analyser)
    analyser.connect(ctx.destination) // 스피커로도 계속 소리가 나가야 해요

    ctxRef.current = ctx
    analyserRef.current = analyser
    bufRef.current = new Uint8Array(analyser.fftSize)
  }, [audio])

  /** 현재 볼륨(RMS)을 0~1 로 정규화해서 반환 */
  const getLevel = useCallback(() => {
    const analyser = analyserRef.current
    const buf = bufRef.current
    if (!analyser || !buf) return 0

    analyser.getByteTimeDomainData(buf)
    let sum = 0
    for (let i = 0; i < buf.length; i++) {
      const v = (buf[i] - 128) / 128 // -1 ~ 1
      sum += v * v
    }
    const rms = Math.sqrt(sum / buf.length)
    // 사람 목소리 RMS 는 보통 0.05 ~ 0.3 정도라 키워서 0~1 범위로 맞춰요
    return Math.min(1, rms * 3.5)
  }, [])

  return { connect, getLevel }
}
