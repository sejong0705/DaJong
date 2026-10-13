"""
DawnAir - write_script
collect_weather + collect_news 결과로 하루치 방송 대본 JSON을 만든다.

LLM 호출 2번 (동시에)
  1) 지역별 날씨 멘트
  2) 뉴스 편성: 톱뉴스 1건 + 카테고리 뉴스, 오프닝/클로징

입력: [collect_weather 결과, collect_news 결과]  (Step Functions Parallel 출력)
  collect_news가 S3에 저장하고 {"bucket", "s3_key"}만 넘기면 S3에서 읽어온다.
  기사 재료는 sources[].body(언론사별 본문)를 우선 쓰고, 본문이 없으면 description을 쓴다.
환경 변수: LLM_BASE_URL, LLM_API_KEY, MODEL_ID(기본 bedrock-haiku)
계층: openai / 타임아웃 5분 / (S3를 쓰면 실행 역할에 s3:GetObject 권한)
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from openai import OpenAI

KST = timezone(timedelta(hours=9))
MODEL_ID = os.environ.get("MODEL_ID", "bedrock-haiku")
CHARS_PER_SEC = 7       # 한국어 TTS 대략적인 읽기 속도
FIRST_BODY_CHARS = 1500  # 사건마다 첫 번째 언론사 본문 길이
OTHER_BODY_CHARS = 500   # 다른 언론사 본문은 보충용으로 짧게 (프롬프트 길이 관리)
WEEKDAYS = "월화수목금토일"

client = OpenAI(
    base_url=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
    timeout=240,
    max_retries=2,
)

# ---------------------------------------------------------------- 프롬프트
SYSTEM_WEATHER = """당신은 아침 라디오 '던에어(DawnAir)'의 날씨 담당 DJ입니다.
지역별 기상청 예보를 받아 그 지역 청취자에게 들려줄 아침 날씨 멘트를 씁니다.

규칙
- 지역마다 2~3문장, 부드러운 라디오 구어체(~요, ~습니다)
- 아침 기온, 낮 최고기온, 비 소식(있으면 몇 시쯤), 일교차를 자연스럽게
- 출근·등교 옷차림 팁 한 문장 포함
- 강수확률 60% 이상이거나 비 오는 시간이 있으면 우산 언급
- 숫자는 읽기 쉽게("12도", "오후 3시쯤"). 괄호·기호·영어 약어 금지
- 데이터에 없는 내용은 지어내지 말 것. 모든 지역 key를 빠짐없이 작성
- "오늘의 날씨입니다" 같은 도입 문장은 쓰지 말고 바로 본론부터 (도입은 코드가 붙임)

JSON 객체 하나만 출력하세요.
{"regions": {"<지역 key>": {"script": "멘트", "summary": "15자 이내 요약", "outfit": "10자 이내 옷차림"}}}"""

SYSTEM_NEWS = """당신은 아침 라디오 '던에어(DawnAir)'의 뉴스 편성 PD이자 DJ입니다.
지난 하루 기사 후보를 받아 오늘 아침 방송을 편성하고 원고를 씁니다.

편성 규칙
- 톱뉴스 1건 + 카테고리 뉴스 9~13건. 카테고리별 개수는 중요도에 따라 유동적(0건도 가능)
- 같은 사건을 다룬 후보는 하나로 합치고 그 id를 모두 ids에 넣을 것. 톱뉴스 기사는 segments에서 반복 금지
- 한 꼭지에는 사건 하나만. 서로 다른 사건을 한 꼭지로 묶지 말 것 (headline에 '·'로 두 사건을 잇는 것 금지)
- 톱뉴스는 coverage(보도 언론사 수)를 참고하되 사회적 파급력을 우선
- 개인 범죄·지역 사건은 사회적 의미가 클 때만, 담담하게. 정치는 균형 있게. 홍보성 기사 제외
- category는 후보에 적힌 이름 그대로

원고 규칙
- headline: 20자 이내
- points: 핵심 요약 3~5문장 (후보 내용이 정말 짧을 때만 2문장).
  각 문장은 서로 다른 사실 하나씩: 무슨 일인지 → 구체적 수치·규모 → 누가·언제부터 → 반응·향후 일정 순으로.
  숫자·기관·장소·날짜를 최대한 살릴 것. 이어서 음성으로 읽히므로 자연스럽게 이어지게
  (음성으로는 points만 읽히니, 청취자가 이것만 듣고도 사건을 이해할 수 있어야 함)
- background: 왜 생긴 일인지 2~3문장 (화면에만 표시)
- why_it_matters: 청취자에게 왜 중요한지 1~2문장 (화면에만 표시)
- 라디오 구어체. 괄호·한자·특수기호·영어 약어는 풀어 쓰기("北"→"북한", "%"→"퍼센트")
- 후보 기사에 있는 사실만 사용. 숫자·발언·날짜를 지어내지 말 것

opening: 오늘 주요 뉴스 예고 2~3문장. 인사·날짜·요일은 쓰지 말 것 (코드가 앞에 붙임). 날씨 언급 금지
closing: 따뜻한 마무리 2문장
title: 톱뉴스를 반영한 방송 제목 25자 이내

JSON 객체 하나만 출력하세요.
{"title": "...", "opening": "...",
 "top": {"ids": ["n1"], "headline": "...", "points": ["..."], "background": "...", "why_it_matters": "..."},
 "segments": [{"category": "...", "ids": ["n2"], "headline": "...", "points": ["..."], "background": "...", "why_it_matters": "..."}],
 "closing": "..."}"""


# ---------------------------------------------------------------- LLM 호출
def ask_json(system, user, max_tokens):
    for attempt in (1, 2):  # 잘리거나 JSON이 깨지면 한 번 더
        r = client.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=0.5,
        )
        choice = r.choices[0]
        text = choice.message.content or ""
        print(f"[{attempt}] finish={choice.finish_reason} usage={r.usage}")
        if choice.finish_reason == "length":
            continue
        try:
            text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
            return json.loads(text[text.find("{"):text.rfind("}") + 1])
        except ValueError:
            print("JSON 파싱 실패:", text[:300])
    raise RuntimeError("LLM 응답에서 JSON을 얻지 못함")


# ---------------------------------------------------------------- 프롬프트 입력 만들기
def to_spoken_hour(h):
    """'19시' → '오후 7시' (모델이 '19시'를 그대로 읽지 않게)"""
    m = re.match(r"(\d{1,2})", str(h))
    if not m:
        return str(h)
    n = int(m.group(1)) % 24
    if n == 0:
        return "밤 12시"
    if n == 12:
        return "낮 12시"
    return f"{'오전' if n < 12 else '오후'} {n % 12}시"


def weather_prompt(weather):
    lines = [f"날짜: {weather['date']}"]
    for r in weather["regions"]:
        parts = [f"[{r['key']}] {r['name']}", f"최저 {r['temp_min']:.0f}도 / 최고 {r['temp_max']:.0f}도"]
        for name, label in (("morning", "아침"), ("afternoon", "오후"), ("evening", "저녁")):
            x = (r.get("periods") or {}).get(name)
            if x:
                parts.append(f"{label} {x['temp_min']:.0f}~{x['temp_max']:.0f}도 {x['sky']} "
                             f"강수 {x['precip']} 확률 {x['pop']}%")
        hours = [to_spoken_hour(h) for h in r.get("rain_hours") or []]
        parts.append(f"비 오는 시간: {', '.join(hours) or '없음'}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def index_candidates(news):
    """기사마다 id(n1, n2…)를 붙인다. 모델은 id만 고르고 링크는 코드가 붙인다."""
    items = ([news["top_news"]] if news.get("top_news") else []) + \
            [a for c in news["categories"] for a in c["articles"]]
    pool, links = {}, set()
    for a in items:
        if a["link"] not in links:
            links.add(a["link"])
            pool[f"n{len(pool) + 1}"] = a
    return pool


def article_text(a):
    """사건 하나의 재료: 언론사별 본문(첫 기사는 길게, 나머지는 짧게). 본문이 없으면 검색 요약문."""
    bodies = [s["body"] for s in a.get("sources") or [] if s.get("body")]
    if bodies:
        parts = [bodies[0][:FIRST_BODY_CHARS]] + [b[:OTHER_BODY_CHARS] for b in bodies[1:]]
    else:
        parts = [a.get("description", "")] + (a.get("related_descriptions") or [])
    return re.sub(r"\s+", " ", " // ".join(p for p in parts if p))


def news_prompt(pool, date_label):
    lines = [f"방송 날짜: {date_label}",
             "기사 후보 (id | 카테고리 | 보도 언론사 수 | 제목 | 내용, 언론사별 본문은 // 로 구분)"]
    for nid, a in pool.items():
        lines.append(f"{nid} | {a['category']} | {a.get('coverage', 1)} | {a['title']} | {article_text(a)}")
    return "\n".join(lines)


def source_links(a):
    """출처 링크 (본문 제외). collect_news의 언론사별 sources가 있으면 그것을, 없으면 대표 기사."""
    srcs = a.get("sources") or [a]
    return [{"press": s.get("press"), "title": s["title"], "link": s["link"],
             "naver_link": s.get("naver_link"), "published": s.get("published")} for s in srcs]


# ---------------------------------------------------------------- 결과 조립
def speech(*parts):
    text = " ".join(p.strip() if p.strip()[-1] in ".!?" else p.strip() + "."
                    for p in parts if p and p.strip())
    # TTS가 기호를 이상하게 읽지 않도록 정리
    for a, b in (("%", "퍼센트"), ("~", "에서 "), ("·", ", "), ("…", ", ")):
        text = text.replace(a, b)
    return text


def build_segment(seg_id, kind, category, raw, pool):
    ids = [i for i in raw.get("ids", []) if i in pool]
    if not ids or not raw.get("headline") or not raw.get("points"):
        return None
    points = raw["points"] if isinstance(raw["points"], list) else [raw["points"]]
    # "IT/과학" → "IT, 과학" (TTS가 슬래시를 읽지 않게)
    lead = "오늘의 톱뉴스입니다." if kind == "top" else f"{category.replace('/', ', ')} 소식입니다."
    text = speech(lead, raw["headline"], *points)  # 음성은 헤드라인 + 요약까지만
    return {
        "id": seg_id, "type": kind, "category": category,
        "headline": raw["headline"], "points": points,
        "background": raw.get("background", ""), "why_it_matters": raw.get("why_it_matters", ""),
        "sources": list({s["link"]: s for i in ids for s in source_links(pool[i])}.values()),
        "speech": text,
        "duration_estimate": round(len(text) / CHARS_PER_SEC),
    }


def build_weather(weather, w):
    out = {}
    for r in weather["regions"]:
        m = w["regions"].get(r["key"], {})
        out[r["key"]] = {
            "name": r["name"], "temp_min": r["temp_min"], "temp_max": r["temp_max"],
            "pop": max((p["pop"] for p in (r.get("periods") or {}).values() if p), default=0),
            "rain_hours": r.get("rain_hours", []),
            "summary": m.get("summary", ""), "outfit": m.get("outfit", ""),
            "speech": speech("오늘의 날씨입니다.", m.get("script")
                             or f"{r['name']}은 아침 {r['temp_min']:.0f}도, 낮 최고 {r['temp_max']:.0f}도입니다."),
        }
    return out


# ---------------------------------------------------------------- 핸들러
def load(x):
    """앞 단계가 S3에 저장하고 위치만 넘겼으면 S3에서 읽어온다."""
    if "s3_key" in x and "regions" not in x and "categories" not in x:
        import boto3
        obj = boto3.client("s3").get_object(Bucket=x["bucket"], Key=x["s3_key"])
        return json.loads(obj["Body"].read())
    return x


def lambda_handler(event, context):
    data = [load(x) for x in event]
    weather = next(x for x in data if "regions" in x)
    news = next(x for x in data if "categories" in x)

    d = datetime.strptime(weather["date"], "%Y-%m-%d")
    date_label = f"{d.month}월 {d.day}일 {WEEKDAYS[d.weekday()]}요일"
    pool = index_candidates(news)
    print(f"지역 {len(weather['regions'])}곳, 뉴스 후보 {len(pool)}건")

    with ThreadPoolExecutor(max_workers=2) as ex:
        fw = ex.submit(ask_json, SYSTEM_WEATHER, weather_prompt(weather), 6000)
        fn = ex.submit(ask_json, SYSTEM_NEWS, news_prompt(pool, date_label), 12000)
        w, n = fw.result(), fn.result()

    segments = [build_segment("top", "top", "오늘의 톱뉴스", n["top"], pool)]
    used = set(n["top"].get("ids", []))
    for s in n.get("segments", []):
        if all(i in used for i in s.get("ids", [])):  # 톱뉴스와 겹치는 꼭지 제외
            continue
        used.update(s.get("ids", []))
        segments.append(build_segment(f"s{len(segments)}", "news", s.get("category", "기타"), s, pool))
    segments = [s for s in segments if s]
    for i, s in enumerate(x for x in segments if x["type"] == "news"):
        s["id"] = f"s{i + 1}"

    weather_out = build_weather(weather, w)
    # 날짜·요일은 모델이 틀릴 수 있어 코드가 직접 붙인다
    opening = f"좋은 아침입니다. {date_label}, 던에어입니다. " + n["opening"]
    closing = n["closing"]
    avg_weather = round(sum(len(v["speech"]) for v in weather_out.values())
                        / len(weather_out) / CHARS_PER_SEC)

    return {
        "date": weather["date"],
        "date_label": date_label,
        "title": n["title"],
        "opening": {"speech": opening, "duration_estimate": round(len(opening) / CHARS_PER_SEC)},
        "weather": weather_out,   # 프론트에서 사용자 지역 key로 골라 재생
        "segments": segments,     # 톱뉴스 → 카테고리 뉴스 순서
        "closing": {"speech": closing, "duration_estimate": round(len(closing) / CHARS_PER_SEC)},
        "duration_estimate": round((len(opening) + len(closing)) / CHARS_PER_SEC)
                             + avg_weather + sum(s["duration_estimate"] for s in segments),
        "generated_at": datetime.now(KST).isoformat(),
        "model": MODEL_ID,
    }