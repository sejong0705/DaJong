// 최소 Service Worker — '앱 설치(홈 화면에 추가)'가 가능하도록 등록만 해요.
// 캐시는 하지 않아요: 항상 네트워크에서 최신 화면 · 방송을 받아옵니다.
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))
self.addEventListener('fetch', () => {
  // 비워 두면 브라우저가 평소처럼 네트워크로 요청해요
})
