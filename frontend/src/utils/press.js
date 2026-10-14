// 언론사 도메인 → 한글 이름
// 백엔드(collect-news)는 기사 링크의 도메인(mk.co.kr 등)을 press 에 넣어 보내요.
// 목록에 없는 언론사는 도메인이 그대로 보이니, 보이면 여기에 한 줄 추가하세요.

const PRESS_NAMES = {
  'mk.co.kr': '매일경제',
  'hankyung.com': '한국경제',
  'sedaily.com': '서울경제',
  'mt.co.kr': '머니투데이',
  'edaily.co.kr': '이데일리',
  'asiae.co.kr': '아시아경제',
  'heraldcorp.com': '헤럴드경제',
  'fnnews.com': '파이낸셜뉴스',
  'biz.chosun.com': '조선비즈',
  'chosun.com': '조선일보',
  'joongang.co.kr': '중앙일보',
  'donga.com': '동아일보',
  'hani.co.kr': '한겨레',
  'khan.co.kr': '경향신문',
  'hankookilbo.com': '한국일보',
  'seoul.co.kr': '서울신문',
  'kmib.co.kr': '국민일보',
  'segye.com': '세계일보',
  'munhwa.com': '문화일보',
  'yna.co.kr': '연합뉴스',
  'yonhapnewstv.co.kr': '연합뉴스TV',
  'news1.kr': '뉴스1',
  'newsis.com': '뉴시스',
  'nocutnews.co.kr': '노컷뉴스',
  'ohmynews.com': '오마이뉴스',
  'pressian.com': '프레시안',
  'kbs.co.kr': 'KBS',
  'imbc.com': 'MBC',
  'sbs.co.kr': 'SBS',
  'ytn.co.kr': 'YTN',
  'jtbc.co.kr': 'JTBC',
  'mbn.co.kr': 'MBN',
  'ichannela.com': '채널A',
  'tvchosun.com': 'TV조선',
  'etnews.com': '전자신문',
  'zdnet.co.kr': '지디넷코리아',
  'dt.co.kr': '디지털타임스',
  'news.naver.com': '네이버뉴스',
}

/**
 * 'news.mk.co.kr' → '매일경제'
 * 앞의 하위 도메인(news., www. 등)을 하나씩 떼면서 목록에서 찾아요.
 */
export function pressName(domain = '') {
  let d = domain.toLowerCase().replace(/^www\./, '')
  while (d.includes('.')) {
    if (PRESS_NAMES[d]) return PRESS_NAMES[d]
    d = d.slice(d.indexOf('.') + 1)
  }
  return domain
}
