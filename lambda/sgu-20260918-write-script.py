"""
DawnAir - write_script
collect_weather + collect_news 결과로 '하루치 방송 대본 JSON'을 만든다.

Bedrock 호출 2번
  1) 지역별 날씨 멘트
  2) 뉴스 편성 — 톱뉴스 1건 + 카테고리별 기사 선별, 요약·배경·왜 중요한가, 오프닝/클로징

입력 (Step Functions에서 받음)
  {"weather": {collect_weather 결과}, "news": {collect_news 결과}}
  ([날씨, 뉴스] 배열로 들어와도 동작)
  collect_news가 S3에 저장하고 {"bucket", "s3_key"}만 넘기면 S3에서 읽어온다.

환경 변수
  LLM_BASE_URL : OpenAI 호환 게이트웨이 주소
  LLM_API_KEY  : 게이트웨이 키
  MODEL_ID     : 기본 bedrock-haiku

Lambda 설정
  런타임 Python / 타임아웃 10분 / 메모리 256MB
  계층: openai
  실행 역할: SafeRole-sgu-20260918 (s3:GetObject 필요)
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone

import boto3
from openai import OpenAI

KST = timezone(timedelta(hours=9))
MODEL_ID = os.environ.get("MODEL_ID", "bedrock-haiku")

CHARS_PER_SEC = 7  # 한국어 TTS 기준 대략적인 읽기 속도 (재생 시간 추정용)
BODY_CHARS = 600   # 프롬프트에 넣을 기사 본문 앞부분 길이 (출처 기사 하나당)

s3 = boto3.client("s3")
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
- 오늘의 톱뉴스 1건 + 카테고리 뉴스 9~13건, 총 10~14건. segments는 최소 9개를 반드시 채울 것 (후보가 충분하면 적게 고르지 말 것)
- 카테고리별 개수는 그날 중요도에 따라 유동적으로 (어떤 카테고리는 1건, 어떤 곳은 4건). 후보가 빈약한 카테고리는 0건도 가능
- 같은 사건·같은 주제를 다룬 후보는 하나로 합쳐서 한 번만 다룰 것
- 카테고리 균형: 정치·경제·사회·국제·IT/과학은 후보가 있으면 최소 1건씩. 환경/기후는 최대 2건

톱뉴스 선정
- 톱뉴스는 반드시 후보 n1(★표시, 가장 많은 언론사가 보도한 사건)로 할 것. 사건·사고여도 그대로 톱뉴스로 다룰 것
- n1과 같은 사건을 다룬 다른 후보가 있으면 top의 ids에 함께 넣고, segments에서 다시 다루지 말 것
- title과 opening도 이 톱뉴스를 중심으로 쓸 것

사건·사고 다루는 법
- 개인 간 범죄·지역 사건은 사회적 의미가 큰 경우에만
- 범행 수단·과정, 피해자·피의자 신상 같은 자극적인 묘사는 summary·points·background 어디에도 쓰지 말 것. 무슨 일이 있었는지와 제도적 쟁점 위주로 담담하게

제외할 기사
- 홍보성 기사: 기업·기관 간 업무협약, 제품 출시, 기업 인사, 지자체의 단순 사업 선정·행사
- 정치 뉴스는 특정 정당·인물 편을 들지 말고 양쪽 입장을 균형 있게

원고 규칙 (기사마다)
- headline: 소리 내 읽을 짧은 제목 (20자 이내)
- summary: 무슨 일이 있었는지 2~3문장 (방송에서 읽는 문장)
- points: 화면에 보여줄 핵심 요약 3~4개. 각 항목은 한 문장으로, 누가·무엇을·얼마나 같은 구체적 사실(숫자, 기관명, 날짜)을 담을 것. 문어체 단문(~했다, ~예정)으로 짧게
- background: 이 일이 왜 생겼는지, 이전 맥락 2~3문장
- why_it_matters: 청취자 삶에 왜 중요한지 1~2문장
- 모두 라디오 구어체(~습니다, ~요). 소리 내 읽기 쉽게: 괄호·한자·특수기호·영어 약어는 풀어 쓰기 (예: "北" → "북한", "美" → "미국", "%" → "퍼센트")
- 후보 기사에 있는 사실만 사용. 널리 알려진 일반 상식 외에 숫자·발언·날짜를 지어내지 말 것. 배경을 모르면 짧게 써도 됨
- 한 꼭지에는 그 꼭지에 고른 후보(ids)의 내용만 쓸 것. 다른 후보 기사의 내용을 섞지 말 것
- 본문 안에 그 사건과 관계없는 문단(같은 인물의 다른 일정, 기사 끝 관련 소식 등)이 섞여 있으면 무시할 것. background는 반드시 이 사건이 왜 일어났는지에 대한 내용이어야 함

오프닝·클로징
- opening: 오늘 주요 뉴스 예고, 2~3문장. "오늘 아침 주요 뉴스를 전해드리겠습니다."처럼 바로 본론으로 시작할 것
  인사말("좋은 아침입니다", "안녕하세요")과 날짜·요일은 쓰지 말 것 (청취자 이름을 넣은 인사가 방송 앞에 자동으로 붙음)
  날씨 언급도 하지 말 것 (날씨 코너가 따로 있음)
- closing: 2문장, 따뜻한 마무리
- title: 오늘 방송 제목 (톱뉴스를 반영, 25자 이내)

반드시 아래 JSON만 출력하세요. 다른 말은 쓰지 마세요.
{
  "title": "...",
  "opening": "...",
  "top": {"ids": ["후보 id", ...], "headline": "...", "summary": "...", "points": ["...", "..."], "background": "...", "why_it_matters": "..."},
  "segments": [
    {"category": "카테고리 이름", "ids": ["후보 id", ...], "headline": "...", "summary": "...", "points": ["...", "..."], "background": "...", "why_it_matters": "..."}
  ],
  "closing": "..."
}
ids에는 그 꼭지에 사용한 후보 기사 id를 모두 넣으세요. segments는 방송 순서대로 정렬하세요."""


# ---------------------------------------------------------------- Bedrock
llm = OpenAI(
    base_url=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
    timeout=240,
    max_retries=2,
)


def call_bedrock(system, user, max_tokens):
    resp = llm.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=0.5,
    )
    choice = resp.choices[0]
    text = choice.message.content or ""
    usage = resp.usage.model_dump() if resp.usage else {}
    stop = "max_tokens" if choice.finish_reason == "length" else choice.finish_reason
    return text, usage, stop


def parse_json(text):
    """```json 코드블록이나 앞뒤 잡담이 붙어 와도 JSON 부분만 꺼낸다."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError(f"JSON을 찾을 수 없음: {text[:200]}")
    return json.loads(text[start:end + 1])


def ask_json(system, user, max_tokens, usage_log):
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
        raise ValueError("입력에 날씨/뉴스 데이터가 없습니다.")
    return weather, load_from_s3(news)


def load_from_s3(data):
    """collect_news가 S3 위치만 넘긴 경우 실제 데이터를 읽어온다."""
    if "categories" in data or "s3_key" not in data:
        return data
    obj = s3.get_object(Bucket=data["bucket"], Key=data["s3_key"])
    return json.loads(obj["Body"].read().decode("utf-8"))


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


def fallback_weather(r):
    """모델이 빠뜨린 지역은 숫자로만 기본 멘트를 만든다."""
    rain = bool(r["rain_hours"])
    return {
        "script": f"{r['name']}은 아침 {r['temp_min']:.0f}도, 낮 최고 {r['temp_max']:.0f}도까지 오릅니다. "
                  + ("비 소식이 있으니 우산 챙기세요." if rain else "얇은 겉옷 하나 챙기시면 좋겠어요."),
        "summary": "비 소식 있어요" if rain else "대체로 맑아요",
        "outfit": "우산 필수" if rain else "얇은 겉옷",
    }


TOP_ID = "n1"  # collect_news가 고른 보도량 1위 사건 (index_candidates에서 맨 앞에 둠)


def fix_top(n, pool):
    """모델이 톱뉴스로 n1을 고르지 않았으면, n1을 다룬 꼭지와 자리를 바꿔 보도량 1위를 톱으로 맞춘다."""
    top, segs = n["top"], n["segments"]
    if TOP_ID not in pool or TOP_ID in top.get("ids", []):
        return
    idx = next((i for i, s in enumerate(segs) if TOP_ID in s.get("ids", [])), None)
    if idx is None:
        return
    new_top = segs.pop(idx)
    first = next((i for i in top.get("ids", []) if i in pool), None)
    top["category"] = pool[first]["category"] if first else new_top["category"]
    segs.insert(0, top)
    n["top"] = new_top


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
    lines = [f"방송 날짜: {date_label}", "",
             "기사 후보 (id | 카테고리 | 보도 언론사 수 | 제목 | 요약), 그 아래 언론사별 본문 앞부분"]
    for nid, a in pool.items():
        desc = " / ".join([a["description"]] + a.get("related_descriptions", []))
        mark = "★" if nid == TOP_ID else ""
        lines.append(f"\n{mark}{nid} | {a['category']} | {a['coverage']} | {a['title']} | {desc}")
        for s in a.get("sources", []):
            body = (s.get("body") or "").replace("\n", " ")[:BODY_CHARS]
            if body:
                lines.append(f"  - [{s.get('press', '')}] {body}")
    return "\n".join(lines)


# ---------------------------------------------------------------- 결과 조립
def speech(*parts):
    return " ".join(p.strip() for p in parts if p and p.strip())


# 오프닝 인사: 대본은 모두에게 하나라서, 청취자 이름 자리는 {nickname} 으로 비워 두고
# 프론트가 재생할 때 로그인한 닉네임으로 바꿔 넣는다.
GREETING_RE = re.compile(r"^(좋은 아침|안녕하세요|안녕하십니까|반갑습니다|\d{4}년|\d{1,2}월\s*\d{1,2}일)")


def opening_body(text):
    """LLM이 프롬프트와 달리 인사·날짜 문장을 앞에 넣었으면 떼어낸다."""
    sentences = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    while sentences and GREETING_RE.match(sentences[0]):
        sentences.pop(0)
    return " ".join(sentences)


def build_segment(seg_id, kind, category, raw, pool):
    ids = [i for i in raw.get("ids", []) if i in pool]
    sources, seen = [], set()
    for i in ids:
        a = pool[i]
        # 언론사별 출처 기사들 (본문 수집에 실패했으면 대표 기사 하나)
        refs = a.get("sources") or [{"press": "", "title": a["title"], "link": a["link"],
                                     "naver_link": a.get("naver_link"), "published": a["published"]}]
        for s in refs:
            if s["link"] not in seen:
                seen.add(s["link"])
                sources.append({"press": s.get("press", ""), "title": s["title"], "link": s["link"],
                                "naver_link": s.get("naver_link"), "published": s["published"]})
    lead = "오늘의 톱뉴스입니다." if kind == "top" else f"{category} 소식입니다."
    text = speech(lead, raw["headline"] + ".", raw["summary"], raw["background"], raw["why_it_matters"])
    return {
        "id": seg_id,
        "type": kind,
        "category": category,
        "headline": raw["headline"],
        "summary": raw["summary"],
        "points": [p for p in raw.get("points", []) if isinstance(p, str) and p.strip()],
        "background": raw["background"],
        "why_it_matters": raw["why_it_matters"],
        "sources": sources,
        "speech": text,
        "duration_estimate": round(len(text) / CHARS_PER_SEC),
    }


def lambda_handler(event, context):
    weather, news = split_input(event)
    date = datetime.strptime(weather["date"], "%Y-%m-%d")
    date_label = f"{date.month}월 {date.day}일 {WEEKDAYS[date.weekday()]}요일"
    usage = []

    # 1) 지역별 날씨
    w = ask_json(SYSTEM_WEATHER, weather_prompt(weather), 6000, usage)
    weather_out = {}
    for r in weather["regions"]:
        m = w.get("regions", {}).get(r["key"]) or fallback_weather(r)
        weather_out[r["key"]] = {
            "name": r["name"], "temp_min": r["temp_min"], "temp_max": r["temp_max"],
            "pop": max((p["pop"] for p in r["periods"].values()), default=0),
            "rain_hours": r["rain_hours"],
            "summary": m["summary"], "outfit": m["outfit"],
            "speech": speech("오늘의 날씨입니다.", m["script"]),
        }

    # 2) 뉴스 편성
    pool = index_candidates(news)
    n = ask_json(SYSTEM_NEWS, news_prompt(pool, date_label), 12000, usage)
    fix_top(n, pool)

    segments = [build_segment("top", "top", "오늘의 톱뉴스", n["top"], pool)]
    for i, s in enumerate(n["segments"], 1):
        segments.append(build_segment(f"s{i}", "news", s["category"], s, pool))

    # 오프닝 = 인사(코드가 만듦) + 본문(LLM)
    #   greeting : "안녕하세요, {nickname}님. 2026년 10월 17일 금요일입니다."  ← 프론트가 닉네임으로 치환
    #   speech   : 닉네임 없는 공용 버전 (Polly 음성 · 예전 화면용)
    today = f"{date.year}년 {date_label}입니다."
    body = opening_body(n["opening"])
    greeting = f"안녕하세요, {{nickname}}님. {today}"
    opening = speech("안녕하세요.", today, body)
    closing = n["closing"]
    news_seconds = sum(s["duration_estimate"] for s in segments)
    avg_weather = round(sum(len(v["speech"]) for v in weather_out.values())
                        / max(len(weather_out), 1) / CHARS_PER_SEC)

    return {
        "date": weather["date"],
        "date_label": date_label,
        "title": n["title"],
        "opening": {
            "speech": opening,
            "greeting": greeting,
            "body": body,
            "duration_estimate": round(len(opening) / CHARS_PER_SEC),
        },
        "weather": weather_out,          # 프론트에서 지역 key로 골라 재생
        "segments": segments,            # 톱뉴스 → 카테고리 뉴스 순서
        "closing": {"speech": closing, "duration_estimate": round(len(closing) / CHARS_PER_SEC)},
        "duration_estimate": round((len(opening) + len(closing)) / CHARS_PER_SEC) + avg_weather + news_seconds,
        "generated_at": datetime.now(KST).isoformat(),
        "model": MODEL_ID,
        "usage": usage,
    }