"""
DawnAir - collect_weather
기상청 단기예보(getVilageFcst)로 시·도 17곳의 '오늘' 날씨를 수집하고
대본 생성(Bedrock)에 넣기 좋은 형태로 요약한다.

환경 변수
  KMA_SERVICE_KEY : 공공데이터포털 서비스키 (반드시 'Decoding' 키를 넣을 것)

Lambda 설정
  런타임 Python 3.12 / 타임아웃 1분 / 메모리 256MB 이상
  실행 역할: SafeRole-sgu-20260918

반환값 (Step Functions 다음 단계로 그대로 전달됨)
  {
    "date": "2026-10-07",
    "base_date": "20261007", "base_time": "0500",
    "regions": [ { "key": "busan", "name": "부산", ... }, ... ],
    "failed":  [ { "key": "jeju", "error": "..." } ]
  }
"""
import json
import os
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ENDPOINT = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

# 시·도 대표 지점 격자 좌표 (공공데이터포털 격자 엑셀로 한 번 확인할 것)
REGIONS = [
    {"key": "seoul",     "name": "서울", "nx": 60,  "ny": 127},
    {"key": "busan",     "name": "부산", "nx": 98,  "ny": 76},
    {"key": "daegu",     "name": "대구", "nx": 89,  "ny": 90},
    {"key": "incheon",   "name": "인천", "nx": 55,  "ny": 124},
    {"key": "gwangju",   "name": "광주", "nx": 58,  "ny": 74},
    {"key": "daejeon",   "name": "대전", "nx": 67,  "ny": 100},
    {"key": "ulsan",     "name": "울산", "nx": 102, "ny": 84},
    {"key": "sejong",    "name": "세종", "nx": 66,  "ny": 103},
    {"key": "gyeonggi",  "name": "경기", "nx": 60,  "ny": 121},
    {"key": "gangwon",   "name": "강원", "nx": 73,  "ny": 134},
    {"key": "chungbuk",  "name": "충북", "nx": 69,  "ny": 107},
    {"key": "chungnam",  "name": "충남", "nx": 68,  "ny": 100},
    {"key": "jeonbuk",   "name": "전북", "nx": 63,  "ny": 89},
    {"key": "jeonnam",   "name": "전남", "nx": 51,  "ny": 67},
    {"key": "gyeongbuk", "name": "경북", "nx": 91,  "ny": 106},
    {"key": "gyeongnam", "name": "경남", "nx": 90,  "ny": 77},
    {"key": "jeju",      "name": "제주", "nx": 52,  "ny": 38},
]

# 단기예보 발표 시각 (발표 후 약 10분 뒤부터 조회 가능)
BASE_TIMES = ["0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"]

SKY = {"1": "맑음", "3": "구름많음", "4": "흐림"}
PTY = {"0": "없음", "1": "비", "2": "비/눈", "3": "눈", "4": "소나기"}
PTY_SEVERITY = {"0": 0, "4": 1, "1": 2, "2": 3, "3": 3}

PERIODS = {
    "morning":   range(6, 12),   # 06~11시
    "afternoon": range(12, 18),  # 12~17시
    "evening":   range(18, 24),  # 18~23시
}


def latest_base(now):
    """지금 시점에 조회 가능한 가장 최근 발표 일자/시각."""
    t = now - timedelta(minutes=15)
    hhmm = t.strftime("%H%M")
    available = [b for b in BASE_TIMES if b <= hhmm]
    if available:
        return t.strftime("%Y%m%d"), available[-1]
    prev = t - timedelta(days=1)
    return prev.strftime("%Y%m%d"), "2300"


def fetch_items(service_key, base_date, base_time, nx, ny, retries=2):
    params = urllib.parse.urlencode({
        "serviceKey": service_key,
        "pageNo": 1,
        "numOfRows": 1000,
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    })
    url = f"{ENDPOINT}?{params}"

    last_err = None
    for attempt in range(retries + 1):
        raw = ""
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            header = data["response"]["header"]
            if header["resultCode"] != "00":
                raise RuntimeError(f"기상청 오류 {header['resultCode']}: {header['resultMsg']}")
            return data["response"]["body"]["items"]["item"]
        except json.JSONDecodeError:
            # 서비스키가 틀리거나 아직 활성화 전이면 JSON이 아니라 XML 에러가 온다
            last_err = RuntimeError(f"JSON 응답 아님(서비스키 확인 필요): {raw[:200]}")
        except Exception as e:  # 네트워크 오류, 일시적 장애 등
            last_err = e
        time.sleep(1 + attempt)
    raise last_err


def summarize(items, target_date):
    """오늘 날짜 예보만 골라 시간대별로 요약."""
    by_hour = {}
    tmn = tmx = None

    for it in items:
        if it["fcstDate"] != target_date:
            continue
        cat, val = it["category"], it["fcstValue"]
        if cat == "TMN":
            tmn = float(val)
            continue
        if cat == "TMX":
            tmx = float(val)
            continue
        hour = int(it["fcstTime"][:2])
        by_hour.setdefault(hour, {})[cat] = val

    if not by_hour:
        raise RuntimeError(f"{target_date} 예보 데이터 없음")

    all_temps = [float(h["TMP"]) for h in by_hour.values() if "TMP" in h]
    # 낮에 테스트하면 이미 지난 TMN/TMX는 안 내려오므로 시간별 기온으로 대체
    if tmn is None and all_temps:
        tmn = min(all_temps)
    if tmx is None and all_temps:
        tmx = max(all_temps)

    periods = {}
    for name, hours in PERIODS.items():
        hs = [by_hour[h] for h in hours if h in by_hour]
        if not hs:
            continue
        temps = [float(h["TMP"]) for h in hs if "TMP" in h]
        sky_code = max((h.get("SKY", "1") for h in hs), key=int)
        pty_code = max((h.get("PTY", "0") for h in hs), key=lambda c: PTY_SEVERITY.get(c, 0))
        periods[name] = {
            "temp_min": min(temps) if temps else None,
            "temp_max": max(temps) if temps else None,
            "sky": SKY.get(sky_code, sky_code),
            "precip": PTY.get(pty_code, pty_code),
            "pop": max(int(h.get("POP", 0)) for h in hs),  # 강수확률(%) 최댓값
        }

    rain_hours = sorted(h for h, v in by_hour.items() if v.get("PTY", "0") != "0")
    winds = [float(h["WSD"]) for h in by_hour.values() if "WSD" in h]

    return {
        "temp_min": tmn,
        "temp_max": tmx,
        "periods": periods,
        "rain_hours": [f"{h}시" for h in rain_hours],
        "wind_max": max(winds) if winds else None,  # m/s
    }


def pick_target_date(now, event):
    """브리핑 대상 날짜.
    - 이벤트에 {"date": "2026-10-07"}가 있으면 그 날짜
    - 18시 이후 실행(저녁 테스트)이면 '내일' 아침 브리핑으로 간주
      (밤에는 오늘 예보가 이미 끝나 데이터가 없음)
    - 그 외(새벽 배치 포함)는 오늘
    """
    if event and event.get("date"):
        return datetime.strptime(event["date"], "%Y-%m-%d").replace(tzinfo=KST)
    if now.hour >= 18:
        return now + timedelta(days=1)
    return now


def lambda_handler(event, context):
    service_key = os.environ["KMA_SERVICE_KEY"]
    now = datetime.now(KST)
    target = pick_target_date(now, event)
    target_date = target.strftime("%Y%m%d")
    base_date, base_time = latest_base(now)

    def work(region):
        items = fetch_items(service_key, base_date, base_time, region["nx"], region["ny"])
        return {"key": region["key"], "name": region["name"], **summarize(items, target_date)}

    regions, failed = [], []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(work, r): r for r in REGIONS}
        for future, region in futures.items():  # REGIONS 순서 유지
            try:
                regions.append(future.result())
            except Exception as e:
                failed.append({"key": region["key"], "error": str(e)})

    # 몇 곳 실패는 넘어가고, 전부 실패하면 Step Functions에서 재시도하도록 에러
    if not regions:
        raise RuntimeError(f"모든 지역 수집 실패: {failed[:3]}")

    return {
        "date": target.strftime("%Y-%m-%d"),
        "base_date": base_date,
        "base_time": base_time,
        "regions": regions,
        "failed": failed,
    }


if __name__ == "__main__":
    # 로컬 테스트: 터미널에서 KMA_SERVICE_KEY 환경 변수 설정 후
    #   python lambda_function.py
    result = lambda_handler({}, None)
    print(json.dumps(result, ensure_ascii=False, indent=2))