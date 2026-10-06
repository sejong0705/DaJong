// 백엔드(API Gateway + Lambda)가 준비되기 전까지 쓰는 목업 데이터예요.
// 필드 구조는 기획서의 DynamoDB 테이블(DawnAirBriefing)과 S3 script.json 을 따릅니다.

import { addDays, currentHourKST, todayKey } from '../utils/date'

const TITLES = [
  '금리 동결, 반도체 반등… 오늘 아침 꼭 알아야 할 5가지',
  '금리 결정 앞두고… 이번 주 시장 체크포인트',
  '주말 사이 달라진 것들: 유가와 환율',
  '연휴 나들이 날씨와 교통 정보',
  'AI 스마트폰 경쟁, 하반기 승자는?',
  '이달부터 달라지는 것들',
]

const SEGMENTS = [
  { start: 0, category: '오프닝', title: '오프닝', text: '좋은 아침입니다, 던에어입니다. 오늘도 출근길을 함께하겠습니다.' },
  { start: 35, category: '날씨', title: '일교차 11도, 옷차림 가이드', text: '서울은 아침 12도로 쌀쌀하게 시작해 낮에는 23도까지 오르겠습니다. 일교차가 큰 만큼 얇은 니트에 가벼운 겉옷 하나 챙기시면 좋겠어요.' },
  { start: 80, category: '경제', title: '기준금리 동결', text: '한국은행이 기준금리를 동결했습니다. 배경을 보면, 물가는 안정세지만 가계부채 증가세가 여전히 부담이라는 판단인데요. 이게 왜 중요하냐면, 대출 금리 인하를 기다리던 분들에겐 조금 더 시간이 필요하다는 신호이기 때문입니다.' },
  { start: 245, category: 'IT', title: '반도체 수출 3개월 연속 증가', text: '반도체 수출이 석 달째 늘었습니다. AI 서버용 메모리 수요가 이끈 결과인데요, 수출 회복이 내수 경기로 이어질지가 다음 관전 포인트입니다.' },
  { start: 450, category: '국제', title: '유럽 AI 규제법 시행', text: '유럽연합의 AI 규제법이 본격 시행에 들어갔습니다. 유럽에 서비스를 내놓는 국내 기업들도 위험 등급에 따른 의무를 지켜야 하는 만큼, 대응 준비가 중요해졌습니다.' },
  { start: 610, category: '사회', title: '대중교통 요금 개편안', text: '대중교통 요금 개편안이 발표됐습니다. 정기권 혜택이 커지는 대신 단거리 기본요금이 오르는 구조라, 내 출퇴근 패턴에 따라 체감이 달라질 수 있습니다.' },
]

const DURATION = 760

function makeBriefing(date, i) {
  return {
    // ---- DynamoDB 속성 ----
    date,
    title: TITLES[i % TITLES.length],
    duration: DURATION - i * 37,
    // public/sample/briefing.mp3 에 아무 mp3나 넣으면 재생 테스트를 할 수 있어요
    audioUrl: '/sample/briefing.mp3',
    weatherSummary: '아침엔 쌀쌀해요. 얇은 니트에 가벼운 겉옷을 챙기세요.',
    headlines: SEGMENTS.filter((s) => s.category !== '오프닝').map((s) => ({
      time: s.start,
      category: s.category,
      title: s.title,
    })),
    // ---- 화면 표시용 추가 정보 (백엔드와 합의 필요) ----
    weather: { region: '서울', sky: '맑음 후 구름', min: 12, max: 23, rainProb: 20 },
    categories: ['경제', 'IT', '국제'],
  }
}

/** 오늘 포함 최근 n일치 목업 (오전 6시 이전이면 오늘 방송은 아직 없음) */
function allBriefings() {
  const today = todayKey()
  const hasToday = currentHourKST() >= 6
  const list = []
  for (let i = hasToday ? 0 : 1; i < 20; i++) {
    list.push(makeBriefing(addDays(today, -i), i))
  }
  return list
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms))

export async function mockGetBriefing(date) {
  await wait(250)
  return allBriefings().find((b) => b.date === date) ?? null
}

export async function mockListBriefings(month) {
  await wait(200)
  return allBriefings().filter((b) => b.date.startsWith(month))
}

export async function mockGetScript(date) {
  await wait(200)
  const b = allBriefings().find((x) => x.date === date)
  return b ? { date, segments: SEGMENTS } : null
}
