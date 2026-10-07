"""
DawnAir - write_script
collect_weather + collect_news 결과로 '하루치 방송 대본 JSON'을 만든다.

Bedrock 호출 2번
  1) 지역별 날씨 멘트 (17개 시·도 한 번에)
  2) 뉴스 편성 — 톱뉴스 1건 + 카테고리별 기사 선별, 요약·배경·왜 중요한가, 오프닝/클로징

입력 (Step Functions Parallel 결과는 [날씨, 뉴스] 배열로 들어옴. 둘 다 지원)
  [ {collect_weather 결과}, {collect_news 결과} ]
  또는 {"weather": {...}, "news": {...}}

환경 변수
  MOCK_BEDROCK : "true"면 Bedrock 대신 가짜 응답 (권한 열리기 전 테스트용)
  MODEL_ID     : 기본 us.anthropic.claude-haiku-4-5-20251001-v1:0
  BEDROCK_REGION : 기본 us-east-1

Lambda 설정
  런타임 Python 3.12 / 타임아웃 5분 / 메모리 256MB
  실행 역할: SafeRole-sgu-20260918
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
MOCK = os.environ.get("MOCK_BEDROCK", "false").strip().strip("'\"").lower() in ("true", "1", "yes", "on")

CHARS_PER_SEC = 7  # 브라우저 한국어 TTS 기준 대략적인 읽기 속도 (재생 시간 추정용)
WEEKDAYS = "월화수목금토일"

# ---------------------------------------------------------------- 프롬프트
SYSTEM_WEATHER = """당신은 아침 라디오 '던에어(DawnAir)'의 날씨 담당 DJ입니다.
지역별 기상청 예보 데이터를 받아, 그 지역 청취자에게 들려줄 아침 날씨 멘트를 씁니다.

규칙
- 지역마다 2~3문장, 부드럽고 다정한 라디오 구어체(~요, ~습니다)
- 아침 기온과 낮 최고기온, 비 소식(있으면 몇 시쯤인지), 일교차를 자연스럽게 녹일 것
- 출근·등교 옷차림 팁을 한 문장 포함 (예: "얇은 겉옷 하나 챙기세요")
- 비 확률 60% 이상이거나 비 예보 시간이 있으면 우산 언급
- 숫자는 소리 내 읽기 쉽게: "12도", "오후 3시쯤". 괄호·기호·영어 약어 쓰지 말 것
- 데이터에 없는 내용(미세먼지 등)은 지어내지 말 것

반드시 아래 JSON만 출력하세요. 다른 말은 쓰지 마세요.
{"regions": {"<지역 key>": {"script": "멘트", "summary": "한 줄 요약 15자 이내", "outfit": "옷차림 10자 이내"}}}"""

SYSTEM_NEWS = """당신은 아침 라디오 '던에어(DawnAir)'의 뉴스 편성 PD이자 DJ입니다.
지난 하루 수집된 기사 후보를 받아 오늘 아침 방송을 편성하고 원고를 씁니다.

편성 규칙
- 오늘의 톱뉴스 1건 + 카테고리 뉴스 9~13건, 총 10~14건
- 카테고리별 개수는 그날 중요도에 따라 유동적으로 (어떤 카테고리는 1건, 어떤 곳은 4건). 후보가 빈약한 카테고리는 0건도 가능
- 같은 사건·같은 주제를 다룬 후보는 하나로 합쳐서 한 번만 다룰 것
- 톱뉴스는 coverage(보도 언론사 수)를 참고하되, 숫자보다 '사회적 파급력·많은 사람의 삶에 미치는 영향'을 우선해 직접 고를 것
- 개인 간 범죄·지역 사건은 사회적 의미가 큰 경우에만. 피해자 신상이나 자극적인 묘사는 빼고 담담하게
- 정치 뉴스는 특정 정당·인물 편을 들지 말고 양쪽 입장을 균형 있게
- 홍보성 기사(기업 인사·제품 소개 등)는 제외

원고 규칙 (기사마다)
- headline: 소리 내 읽을 짧은 제목 (20자 이내)
- summary: 무슨 일이 있었는지 2~3문장
- background: 이 일이 왜 생겼는지, 이전 맥락 2~3문장
- why_it_matters: 청취자 삶에 왜 중요한지 1~2문장
- 모두 라디오 구어체(~습니다, ~요). 소리 내 읽기 쉽게: 괄호·한자·특수기호·영어 약어는 풀어 쓰기 (예: "北" → "북한", "美" → "미국", "%" → "퍼센트")
- 후보 기사에 있는 사실만 사용. 널리 알려진 일반 상식 외에 숫자·발언·날짜를 지어내지 말 것. 배경을 모르면 짧게 써도 됨

오프닝·클로징
- opening: 날짜·요일 인사 + 오늘 주요 뉴스 예고, 3~4문장. 날씨 언급은 하지 말 것 (날씨 코너가 따로 있음)
- closing: 2문장, 따뜻한 마무리
- title: 오늘 방송 제목 (톱뉴스를 반영, 25자 이내)

반드시 아래 JSON만 출력하세요. 다른 말은 쓰지 마세요.
{
  "title": "...",
  "opening": "...",
  "top": {"ids": ["후보 id", ...], "headline": "...", "summary": "...", "background": "...", "why_it_matters": "..."},
  "segments": [
    {"category": "카테고리 이름", "ids": ["후보 id", ...], "headline": "...", "summary": "...", "background": "...", "why_it_matters": "..."}
  ],
  "closing": "..."
}
ids에는 그 꼭지에 사용한 후보 기사 id를 모두 넣으세요. segments는 방송 순서대로 정렬하세요."""


# ---------------------------------------------------------------- Bedrock
_client = None


def call_bedrock(system, user, max_tokens):
    global _client
    import boto3
    from botocore.config import Config
    if _client is None:
        _client = boto3.client(
            "bedrock-runtime", region_name=BEDROCK_REGION,
            config=Config(read_timeout=240, retries={"max_attempts": 3, "mode": "adaptive"}),
        )
    resp = _client.converse(
        modelId=MODEL_ID,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.5},
    )
    text = "".join(c.get("text", "") for c in resp["output"]["message"]["content"])
    return text, resp.get("usage", {}), resp.get("stopReason")


def parse_json(text):
    """```json 코드블록이나 앞뒤 잡담이 붙어 와도 JSON 부분만 꺼낸다."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError(f"JSON을 찾을 수 없음: {text[:200]}")
    return json.loads(text[start:end + 1])


def ask_json(system, user, max_tokens, mock_fn, usage_log):
    if MOCK:
        return mock_fn()
    last_err = None
    for _ in range(2):  # JSON이 깨지면 한 번 더
        text, usage, stop = call_bedrock(system, user, max_tokens)
        usage_log.append(usage)
        if stop == "max_tokens":
            last_err = RuntimeError("응답이 maxTokens에서 잘림")
            continue
        try:
            return parse_json(text)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Bedrock 응답 파싱 실패: {last_err}")


# ---------------------------------------------------------------- 입력 정리
def split_input(event):
    weather = news = None
    if isinstance(event, list):
        weather = next((x for x in event if isinstance(x, dict) and "regions" in x), None)
        news = next((x for x in event if isinstance(x, dict) and "categories" in x), None)
    elif isinstance(event, dict):
        weather, news = event.get("weather"), event.get("news")
    if not weather or not news:
        raise ValueError(
            "입력에 날씨/뉴스 데이터가 없습니다. 테스트 이벤트에 "
            "[collect_weather 결과, collect_news 결과] 배열을 넣거나 test_event.json을 붙여넣으세요.")
    return weather, news


def weather_prompt(weather):
    lines = []
    for r in weather["regions"]:
        p = r.get("periods", {})
        def fmt(name, label):
            x = p.get(name)
            if not x:
                return f"{label}: 정보 없음"
            return (f"{label}: {x['temp_min']:.0f}~{x['temp_max']:.0f}도, {x['sky']}, "
                    f"강수형태 {x['precip']}, 강수확률 최대 {x['pop']}%")
        lines.append(
            f"[{r['key']}] {r['name']} | 최저 {r['temp_min']:.0f}도 / 최고 {r['temp_max']:.0f}도 | "
            f"{fmt('morning', '아침')} | {fmt('afternoon', '오후')} | {fmt('evening', '저녁')} | "
            f"비 오는 시간: {', '.join(r['rain_hours']) or '없음'} | 최대 풍속 {r.get('wind_max') or 0}m/s"
        )
    return f"날짜: {weather['date']}\n\n" + "\n".join(lines)


def index_candidates(news):
    """후보 기사에 id(n1, n2 …)를 붙인다. 모델은 id만 고르고, 링크는 코드가 붙인다(링크 지어내기 방지)."""
    pool, n = {}, 0
    top = news.get("top_news")
    items = ([top] if top else []) + [a for c in news["categories"] for a in c["articles"]]
    for a in items:
        n += 1
        pool[f"n{n}"] = a
    return pool


def news_prompt(pool, date_label):
    lines = [f"방송 날짜: {date_label}", "", "기사 후보 (id | 카테고리 | 보도 언론사 수 | 제목 | 내용)"]
    for nid, a in pool.items():
        body = " / ".join([a["description"]] + a.get("related_descriptions", []))
        lines.append(f"{nid} | {a['category']} | {a['coverage']} | {a['title']} | {body}")
    return "\n".join(lines)


# ---------------------------------------------------------------- 가짜 응답 (MOCK)
def mock_weather(weather):
    out = {}
    for r in weather["regions"]:
        rain = bool(r["rain_hours"])
        out[r["key"]] = {
            "script": f"{r['name']}은 아침 {r['temp_min']:.0f}도, 낮 최고 {r['temp_max']:.0f}도까지 오릅니다. "
                      + ("비 소식이 있으니 우산 챙기세요." if rain else "얇은 겉옷 하나 챙기시면 좋겠어요."),
            "summary": "비 소식 있어요" if rain else "대체로 맑아요",
            "outfit": "우산 필수" if rain else "얇은 겉옷",
        }
    return {"regions": out}


def mock_news(pool):
    ids = list(pool)
    top_id, rest = ids[0], ids[1:12]
    seg = lambda i: {"category": pool[i]["category"], "ids": [i],
                     "headline": pool[i]["title"][:20],
                     "summary": pool[i]["description"][:120],
                     "background": "[가짜 응답] 배경 설명 자리입니다.",
                     "why_it_matters": "[가짜 응답] 왜 중요한지 설명 자리입니다."}
    top = seg(top_id)
    top.pop("category")
    return {"title": f"[테스트] {pool[top_id]['title'][:20]}",
            "opening": "[가짜 응답] 좋은 아침입니다. 던에어 아침 브리핑을 시작합니다.",
            "top": top, "segments": [seg(i) for i in rest],
            "closing": "[가짜 응답] 오늘도 좋은 하루 보내세요."}


# ---------------------------------------------------------------- 결과 조립
def speech(*parts):
    return " ".join(p.strip() for p in parts if p and p.strip())


def build_segment(seg_id, kind, category, raw, pool):
    ids = [i for i in raw.get("ids", []) if i in pool]
    sources, seen = [], set()
    for i in ids:
        a = pool[i]
        if a["link"] not in seen:
            seen.add(a["link"])
            sources.append({"title": a["title"], "link": a["link"],
                            "naver_link": a.get("naver_link"), "published": a["published"]})
    lead = "오늘의 톱뉴스입니다." if kind == "top" else f"{category} 소식입니다."
    text = speech(lead, raw["headline"] + ".", raw["summary"], raw["background"], raw["why_it_matters"])
    return {
        "id": seg_id,
        "type": kind,
        "category": category,
        "headline": raw["headline"],
        "summary": raw["summary"],
        "background": raw["background"],
        "why_it_matters": raw["why_it_matters"],
        "sources": sources,
        "speech": text,
        "duration_estimate": round(len(text) / CHARS_PER_SEC),
    }


def lambda_handler(event, context):
    print(f"MOCK_BEDROCK={os.environ.get('MOCK_BEDROCK')!r} → {'가짜 응답 모드' if MOCK else 'Bedrock 호출 모드'}")
    weather, news = split_input(event)
    date = datetime.strptime(weather["date"], "%Y-%m-%d")
    date_label = f"{date.month}월 {date.day}일 {WEEKDAYS[date.weekday()]}요일"
    usage = []

    # 1) 지역별 날씨
    w = ask_json(SYSTEM_WEATHER, weather_prompt(weather), 6000,
                 lambda: mock_weather(weather), usage)
    weather_out = {}
    for r in weather["regions"]:
        m = w["regions"].get(r["key"])
        if not m:  # 모델이 빠뜨린 지역은 숫자로만 기본 멘트
            m = mock_weather({"regions": [r]})["regions"][r["key"]]
        weather_out[r["key"]] = {
            "name": r["name"], "temp_min": r["temp_min"], "temp_max": r["temp_max"],
            "pop": max((p["pop"] for p in r["periods"].values()), default=0),
            "rain_hours": r["rain_hours"],
            "summary": m["summary"], "outfit": m["outfit"],
            "speech": speech("오늘의 날씨입니다.", m["script"]),
        }

    # 2) 뉴스 편성
    pool = index_candidates(news)
    n = ask_json(SYSTEM_NEWS, news_prompt(pool, date_label), 12000,
                 lambda: mock_news(pool), usage)

    segments = [build_segment("top", "top", "오늘의 톱뉴스", n["top"], pool)]
    for i, s in enumerate(n["segments"], 1):
        segments.append(build_segment(f"s{i}", "news", s["category"], s, pool))

    opening = n["opening"]
    closing = n["closing"]
    news_seconds = sum(s["duration_estimate"] for s in segments)
    avg_weather = round(sum(len(v["speech"]) for v in weather_out.values())
                        / max(len(weather_out), 1) / CHARS_PER_SEC)

    return {
        "date": weather["date"],
        "date_label": date_label,
        "title": n["title"],
        "opening": {"speech": opening, "duration_estimate": round(len(opening) / CHARS_PER_SEC)},
        "weather": weather_out,          # 프론트에서 사용자 지역 key로 골라 재생
        "segments": segments,            # 톱뉴스 → 카테고리 뉴스 순서
        "closing": {"speech": closing, "duration_estimate": round(len(closing) / CHARS_PER_SEC)},
        "duration_estimate": round((len(opening) + len(closing)) / CHARS_PER_SEC) + avg_weather + news_seconds,
        "generated_at": datetime.now(KST).isoformat(),
        "model": "mock" if MOCK else MODEL_ID,
        "usage": usage,
    }