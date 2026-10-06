# DawnAir 프론트엔드

매일 아침 6시, 날씨와 뉴스의 배경까지 라디오처럼 들려주는 모닝 브리핑 웹앱의 프론트엔드예요.
React + Vite 로 만들었고 AWS Amplify 로 배포합니다.

- 디자인: [피그마 와이어프레임](https://www.figma.com/design/jwxaZM0g5ETLebqh9678vd)

## 실행하기

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

- `npm run build` : 배포용 빌드 (`dist/`)
- `npm run preview` : 빌드 결과 미리보기

재생을 테스트하려면 아무 mp3 를 `public/sample/briefing.mp3` 로 넣어 주세요.

## 폴더 구조

```
src/
├─ api/            데이터 조회 (briefing.js: 실제 API / mock.js: 목업)
├─ components/     공통 컴포넌트 (피그마 컴포넌트와 이름을 맞춤)
│   ├─ Logo                  로고 + 등장 애니메이션
│   ├─ BroadcastOrb          방송 화면 태양 (목소리 볼륨에 반응)
│   ├─ BriefingItems         CategoryChip · HeadlineItem · EpisodeItem
│   ├─ Navigation            TopNav(데스크톱) · BottomNav(모바일) · 테마 전환
│   └─ PlayerDock            PlayerBar(데스크톱) · MiniPlayer(모바일)
├─ context/        PlayerContext — 앱 전체가 공유하는 오디오 플레이어
├─ hooks/          useAudioAnalyser(볼륨 측정) · useTheme · useAsync
├─ pages/          화면 (홈 · 대본 · 지난 방송 · 방송 화면)
├─ styles/         tokens.css(디자인 토큰 · 라이트/다크) · global.css
└─ utils/          날짜 · 시간 포맷 (한국 시간 기준)
```

## 디자인 토큰 · 라이트/다크 모드

`src/styles/tokens.css` 의 CSS 변수는 피그마 변수 이름과 1:1로 맞췄어요. (`bg/page` → `--bg-page`)

- 기본은 OS 설정을 따르고, 헤더의 해/달 버튼으로 직접 바꿀 수 있어요.
- 색을 바꿀 때는 피그마 변수와 `tokens.css` 를 같이 바꿔 주세요.

## 반응형 기준

| 폭 | 레이아웃 |
| --- | --- |
| 1024px 이상 | 데스크톱 (2단 레이아웃, 상단 헤더 + 하단 전체 폭 재생바) |
| 768 ~ 1023px | 태블릿 (1단 레이아웃, 데스크톱 내비게이션) |
| 767px 이하 | 모바일 (하단 탭바 + 미니 플레이어) |

## 백엔드 연결

`.env.example` 을 `.env` 로 복사하고 값을 채우면 목업 대신 실제 API 를 써요.

| 변수 | 내용 |
| --- | --- |
| `VITE_API_BASE_URL` | API Gateway 주소 (DynamoDB 메타데이터 조회) |
| `VITE_ASSET_BASE_URL` | CloudFront 주소 (script.json · mp3) |

정적 페이지에서는 DynamoDB 를 직접 조회할 수 없어서 **API Gateway + Lambda** 가 필요해요.
예상 API 형태는 `src/api/briefing.js` 맨 위 주석을 참고해 주세요.

### ⚠️ 오디오 CORS 설정 (꼭 필요)

방송 화면의 orb 는 Web Audio API 의 `AnalyserNode` 로 목소리 볼륨을 읽어요.
오디오가 CloudFront 등 다른 도메인에 있으면 **S3 버킷과 CloudFront 에 CORS 를 허용**해야 합니다.
CORS 가 없으면 소리가 **무음**으로 나와요.

S3 CORS 예시:

```json
[
  {
    "AllowedOrigins": ["https://<amplify-도메인>", "http://localhost:5173"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["Content-Length", "Content-Range", "Accept-Ranges"]
  }
]
```

CloudFront 는 응답 헤더 정책에서 CORS 를 허용하고, 캐시 키에 `Origin` 헤더를 포함해 주세요.

## Amplify 설정

- 빌드 설정은 저장소 루트의 `amplify.yml` 을 사용해요 (`frontend` 폴더 → `dist` 배포).
- **주소 직접 접속(새로고침) 대비 리라이트 규칙**을 Amplify 콘솔 → *Rewrites and redirects* 에 추가해 주세요.
  - Source: `</^[^.]+$|\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webmanifest|mp3)$)([^.]+$)/>`
  - Target: `/index.html`
  - Type: `200 (Rewrite)`
  - 이 규칙이 없으면 `/history` 같은 주소로 바로 들어갈 때 404 가 나요.
