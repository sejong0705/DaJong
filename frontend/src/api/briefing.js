// 브리핑 데이터 조회
//
// 정적 페이지(S3/Amplify)에서는 DynamoDB 를 직접 조회할 수 없어서
// API Gateway + Lambda 로 만든 읽기 전용 API 를 호출해요.
//
// .env 파일에 아래 값을 넣으면 실제 API 를 사용하고, 비어 있으면 목업 데이터를 씁니다.
//   VITE_API_BASE_URL=https://xxxx.execute-api.ap-northeast-2.amazonaws.com/prod
//   VITE_ASSET_BASE_URL=https://xxxx.cloudfront.net
//
// 예상 API 형태 (백엔드 팀과 맞춰 주세요)
//   GET {API}/briefings/{YYYY-MM-DD}       → DynamoDB 아이템 1개 (없으면 404)
//   GET {API}/briefings?month=YYYY-MM       → 해당 월 아이템 배열
//   GET {ASSET}/scripts/YYYY/MM/DD/script.json → 대본 JSON

import { mockGetBriefing, mockGetScript, mockListBriefings } from './mock'

const API_BASE = import.meta.env.VITE_API_BASE_URL
const ASSET_BASE = import.meta.env.VITE_ASSET_BASE_URL

export const isMock = !API_BASE

async function getJson(url) {
  const res = await fetch(url)
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`요청 실패 (${res.status})`)
  return res.json()
}

export function getBriefing(date) {
  if (isMock) return mockGetBriefing(date)
  return getJson(`${API_BASE}/briefings/${date}`)
}

export async function listBriefings(month) {
  if (isMock) return mockListBriefings(month)
  const data = await getJson(`${API_BASE}/briefings?month=${month}`)
  return data ?? []
}

export function getScript(date) {
  if (isMock || !ASSET_BASE) return mockGetScript(date)
  const [y, m, d] = date.split('-')
  return getJson(`${ASSET_BASE}/scripts/${y}/${m}/${d}/script.json`)
}
