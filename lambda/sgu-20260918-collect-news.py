"""
DawnAir - collect_news
NAVER API HUB 뉴스 검색으로 '오늘의 톱뉴스' + 카테고리별 주요 사건을 고르고,
사건마다 언론사가 다른 기사 2~3개의 '본문'까지 가져와서 다음 단계(write_script)에 넘긴다.

동작 방식
  1) 카테고리마다 키워드 여러 개로 최신 기사를 검색 (기간 안의 기사를 여러 페이지에 걸쳐 수집)
  2) 네이버 뉴스 링크의 섹션 번호(sid)로 진짜 카테고리를 판별
     (sid=100 정치, 101 경제, 102 사회, 103 생활/문화, 104 세계, 105 IT/과학)
  3) 제목이 비슷한 기사를 같은 사건으로 묶고, 여러 언론사가 다룬 사건일수록 중요하다고 판단
  4) 전체에서 가장 많이 보도된 사건을 '오늘의 톱뉴스'로 선정
  5) 고른 사건마다 언론사가 다른 기사 최대 3개를 골라 네이버 뉴스 페이지에서 본문 수집
  6) 결과를 S3에 저장 (BUCKET 환경 변수가 없으면 결과를 그대로 반환 — 콘솔 테스트용)

최종적으로 몇 건을 방송할지(카테고리별 배분)는 다음 단계 write_script에서 Bedrock이 정한다.

환경 변수
  NAVER_CLIENT_ID     : NAVER API HUB Client ID
  NAVER_CLIENT_SECRET : NAVER API HUB Client Secret
  BUCKET (선택)       : 결과를 저장할 S3 버킷. 없으면 결과를 응답으로 바로 반환

Lambda 설정
  런타임 Python 3.12 / 타임아웃 3분 / 메모리 256MB
  실행 역할: SafeRole-sgu-20260918 (BUCKET을 쓰면 s3:PutObject 권한 필요)

테스트 이벤트 (선택)
  {}                                         기본값
  {"hours": 24, "top_n": 6, "max_pages": 3}  최근 몇 시간 / 카테고리당 후보 수 / 키워드당 검색 페이지 수
  {"skip_body": true}                        본문 수집 생략 (검색·묶기만 빠르게 확인)
"""
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

KST = timezone(timedelta(hours=9))
ENDPOINT = "https://naverapihub.apigw.ntruss.com/search/v1/news"

# 카테고리 정의 — keywords: 검색어, sids: 인정할 네이버 섹션 번호
# 순서가 우선순위: 한 사건이 여러 카테고리에 걸리면 앞쪽 카테고리에 배정
#   title_terms(선택): 제목에 이 단어 중 하나가 있어야 인정
#   (환경 키워드는 본문에만 살짝 들어간 기사가 많이 걸려서 제목으로 한 번 더 거름)
CATEGORIES = [
    {"key": "climate", "name": "환경/기후",
     "keywords": ["기후변화", "기후위기", "탄소중립", "폭염", "미세먼지", "재생에너지"],
     "sids": {"101", "102", "103", "104", "105"},
     "title_terms": ["기후", "탄소", "온실가스", "폭염", "폭우", "호우", "태풍", "가뭄", "산불",
                     "미세먼지", "재생에너지", "환경", "플라스틱", "생태", "멸종", "해수면", "빙하"]},
    {"key": "politics", "name": "정치",
     "keywords": ["대통령실", "국회", "여야", "국정감사", "북한", "외교부"],
     "sids": {"100"}},
    {"key": "economy", "name": "경제",
     "keywords": ["경제", "금리", "증시", "환율", "부동산", "물가", "수출"],
     "sids": {"101"}},
    {"key": "society", "name": "사회",
     "keywords": ["경찰", "법원", "사고", "교육", "노동", "복지"],
     "sids": {"102"}},
    {"key": "world", "name": "국제",
     "keywords": ["국제", "백악관", "중국 정부", "일본 정부", "유럽", "중동"],
     "sids": {"104"}},
    {"key": "it", "name": "IT/과학",
     "keywords": ["인공지능", "반도체", "과학기술", "우주", "빅테크", "보안"],
     "sids": {"105"}},
]

DISPLAY = 100             # 한 번에 가져올 기사 수 (최대 100)
TITLE_SIM = 0.45          # 제목 유사도가 이 이상이면 같은 사건
DESC_SIM = 0.30           # 제목+요약문 유사도가 이 이상이면 같은 사건 (제목 표현이 다를 때 보완)
SOURCES_PER_EVENT = 3     # 사건마다 본문을 가져올 기사 수 (언론사가 다른 것으로)
MIN_BODY_LEN = 200        # 이보다 짧은 본문(포토·영상 기사)은 버림
MAX_BODY_LEN = 3000       # 기사 하나당 본문 최대 글자 수 (Bedrock 비용 관리)

# 방송 재료가 안 되는 기사 (인사·부고·포토·날씨 등). 날씨는 기상청 데이터로 따로 다룸
JUNK_RE = re.compile(r"^\s*[\[【(<]\s*(인사|부고|부음|동정|포토|사진|화보|게시판|알림|모집|표|그래픽|"
                     r"날씨|내일\s*날씨|오늘\s*날씨|주말\s*날씨|운세|오늘의\s*운세|광고|AD)")
TAG_RE = re.compile(r"<[^>]+>")
NON_WORD_RE = re.compile(r"[^0-9A-Za-z가-힣]")


# ---------------------------------------------------------------- 수집
def search(query, client_id, client_secret, start=1, retries=2):
    params = urllib.parse.urlencode({
        "query": query,
        "display": DISPLAY,
        "start": start,
        "sort": "date",
        "format": "json",
    })
    req = urllib.request.Request(
        f"{ENDPOINT}?{params}",
        headers={
            "X-NCP-APIGW-API-KEY-ID": client_id,
            "X-NCP-APIGW-API-KEY": client_secret,
        },
    )
    last_err = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8")).get("items", [])
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:300]
            if e.code in (401, 403):  # 키 문제는 재시도해도 소용없음
                raise RuntimeError(f"인증 실패({e.code}) — Client ID/Secret 확인: {body}")
            last_err = RuntimeError(f"HTTP {e.code}: {body}")
        except Exception as e:
            last_err = e
        time.sleep(1 + attempt)
    raise last_err


def search_period(query, client_id, client_secret, since, max_pages):
    """최신순으로 페이지를 넘기며, 기간(since)보다 오래된 기사가 나오면 멈춤.
    '경제'처럼 기사가 많은 키워드는 100개가 몇 시간 만에 차기 때문에 여러 페이지가 필요함."""
    items = []
    for page in range(max_pages):
        start = 1 + page * DISPLAY
        if start > 1000:  # API 최대 start
            break
        batch = search(query, client_id, client_secret, start=start)
        items.extend(batch)
        if len(batch) < DISPLAY:
            break
        try:
            if parsedate_to_datetime(batch[-1]["pubDate"]) < since:
                break
        except Exception:
            break
    return items


# ---------------------------------------------------------------- 정리
def clean(text):
    """<b> 태그, &quot; 같은 HTML 엔티티 제거."""
    return html.unescape(TAG_RE.sub("", text or "")).strip()


def naver_sid(link):
    """n.news.naver.com 링크에서 섹션 번호 추출. 스포츠·연예·제휴 외 언론사는 None."""
    if not link or "n.news.naver.com" not in link:
        return None
    return urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("sid", [None])[0]


def press_domain(link):
    return urllib.parse.urlparse(link or "").netloc.replace("www.", "")


def bigrams(title):
    s = NON_WORD_RE.sub("", title.lower())
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


def containment(a, b):
    return len(a & b) / min(len(a), len(b)) if a and b else 0


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0


def same_event(x, y):
    """기사 두 개가 같은 사건인지. x, y는 normalize()한 기사."""
    return (containment(x["t_grams"], y["t_grams"]) >= TITLE_SIM
            or jaccard(x["d_grams"], y["d_grams"]) >= DESC_SIM)


def same_cluster(art, members):
    return any(same_event(art, m) for m in members)


def normalize(item, since):
    sid = naver_sid(item.get("link"))
    if sid is None:
        return None
    try:
        published = parsedate_to_datetime(item["pubDate"]).astimezone(KST)
    except Exception:
        return None
    title = clean(item.get("title"))
    if not title or published < since or JUNK_RE.match(title):
        return None
    description = clean(item.get("description"))
    return {
        "title": title,
        "description": description,
        "link": item.get("originallink") or item.get("link"),
        "naver_link": item.get("link"),
        "sid": sid,
        "published": published,
        "t_grams": bigrams(title),
        "d_grams": bigrams(title + description),
    }


def cluster(articles):
    """같은 사건을 다룬 기사끼리 묶는다. 묶인 기사 중 하나라도 비슷하면 같은 묶음."""
    clusters = []
    for art in sorted(articles, key=lambda a: a["published"], reverse=True):
        domain = press_domain(art["link"])
        for c in clusters:
            if same_cluster(art, c["related"]):
                c["count"] += 1
                c["sources"].add(domain)
                c["related"].append(art)
                # 설명이 더 긴 기사를 대표로 (대본 재료가 풍부하도록)
                if len(art["description"]) > len(c["rep"]["description"]):
                    c["rep"] = art
                break
        else:
            clusters.append({"rep": art, "count": 1, "sources": {domain}, "related": [art]})
    return clusters


def pick_sources(c, n=SOURCES_PER_EVENT):
    """같은 사건 기사 중 언론사가 다른 것 n개. 대표 기사를 먼저, 나머지는 설명이 긴 순.
    본문 수집에 실패할 것에 대비해 여유분(n*2)까지 후보로 둔다."""
    ordered = [c["rep"]] + sorted((a for a in c["related"] if a is not c["rep"]),
                                  key=lambda a: len(a["description"]), reverse=True)
    picked, domains = [], set()
    for a in ordered:
        d = press_domain(a["link"])
        if d in domains:
            continue
        domains.add(d)
        picked.append({
            "press": d,
            "title": a["title"],
            "link": a["link"],
            "naver_link": a["naver_link"],
            "published": a["published"].isoformat(),
        })
        if len(picked) >= n * 2:
            break
    return picked


def to_output(c, category):
    rep = c["rep"]
    # 같은 사건을 다룬 다른 기사 설명도 몇 개 붙여서, 본문 수집이 실패해도 최소한의 재료가 남도록
    # (통신사 기사를 그대로 받아쓴 거의 같은 문장은 제외)
    extra, kept = [], [bigrams(rep["description"])]
    for a in c["related"]:
        if a is rep or not a["description"]:
            continue
        g = bigrams(a["description"])
        if all(jaccard(g, k) < 0.6 for k in kept):
            extra.append(a["description"])
            kept.append(g)
        if len(extra) >= 2:
            break
    return {
        "category": category["name"],
        "title": rep["title"],
        "description": rep["description"],
        "related_descriptions": extra,
        "link": rep["link"],
        "naver_link": rep["naver_link"],
        "published": rep["published"].isoformat(),
        "coverage": len(c["sources"]),  # 몇 개 언론사가 다뤘는지
        "sources": pick_sources(c),     # 본문 수집 후 SOURCES_PER_EVENT개로 정리됨
    }


# ---------------------------------------------------------------- 본문
class BodyParser(HTMLParser):
    """네이버 뉴스 페이지에서 id="dic_area" 안의 텍스트만 추출 (사진 설명·표·스크립트 제외)."""

    # 닫는 태그가 없는 태그 — 깊이 계산에서 빼야 본문 밖 텍스트가 섞이지 않음
    VOID = {"br", "img", "hr", "input", "meta", "source", "wbr", "embed", "link",
            "area", "col", "track", "param", "base"}
    SKIP = {"script", "style", "figure", "figcaption", "table", "button"}

    def __init__(self):
        super().__init__()
        self.depth = 0   # dic_area 안에서의 깊이 (0이면 밖)
        self.skip = 0    # 건너뛸 영역 깊이
        self.parts = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.depth == 0:
            if a.get("id") == "dic_area":
                self.depth = 1
            return
        if tag in self.VOID:
            if tag in ("br", "hr"):
                self.parts.append("\n")
            return
        self.depth += 1
        cls = a.get("class") or ""
        if self.skip or tag in self.SKIP or "img_desc" in cls or "end_photo" in cls:
            self.skip += 1

    def handle_endtag(self, tag):
        if self.depth == 0 or tag in self.VOID:
            return
        self.depth -= 1
        if self.skip:
            self.skip -= 1
        elif tag in ("p", "div"):
            self.parts.append("\n")

    def handle_data(self, data):
        if self.depth > 0 and not self.skip:
            self.parts.append(data)

    def text(self):
        body = re.sub(r"[ \t\xa0]+", " ", "".join(self.parts))
        body = re.sub(r"\n\s*\n+", "\n", body)
        return body.strip()


def fetch_body(naver_link):
    req = urllib.request.Request(naver_link, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        page = resp.read().decode("utf-8", "ignore")
    parser = BodyParser()
    parser.feed(page)
    return parser.text()[:MAX_BODY_LEN]


def attach_bodies(events, failed):
    """모든 사건의 출처 후보 본문을 병렬로 가져와서, 사건마다 본문 있는 기사 SOURCES_PER_EVENT개만 남김."""
    links = {s["naver_link"] for ev in events for s in ev["sources"]}

    def safe_fetch(link):
        try:
            return link, fetch_body(link)
        except Exception as e:
            failed.append({"body": link, "error": str(e)[:200]})
            return link, ""

    with ThreadPoolExecutor(max_workers=8) as pool:
        bodies = dict(pool.map(safe_fetch, links))

    for ev in events:
        kept = []
        for s in ev["sources"]:
            body = bodies.get(s["naver_link"], "")
            if len(body) >= MIN_BODY_LEN:
                kept.append({**s, "body": body})
            if len(kept) >= SOURCES_PER_EVENT:
                break
        ev["sources"] = kept
        ev["has_body"] = bool(kept)  # False면 write_script는 description들만으로 짧게 다뤄야 함


# ---------------------------------------------------------------- 핸들러
def lambda_handler(event, context):
    event = event or {}
    client_id = os.environ["NAVER_CLIENT_ID"]
    client_secret = os.environ["NAVER_CLIENT_SECRET"]
    hours = int(event.get("hours", 24))
    top_n = int(event.get("top_n", 6))
    max_pages = int(event.get("max_pages", 3))
    # "false"(문자열)도 True로 읽히지 않도록 직접 판별
    skip_body = str(event.get("skip_body", False)).strip().lower() in ("true", "1", "yes")

    now = datetime.now(KST)
    since = now - timedelta(hours=hours)

    # 모든 키워드 병렬 검색
    jobs = [(cat["key"], kw) for cat in CATEGORIES for kw in cat["keywords"]]
    raw = {cat["key"]: [] for cat in CATEGORIES}
    failed = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(search_period, kw, client_id, client_secret, since, max_pages): (key, kw)
                   for key, kw in jobs}
        for future, (key, kw) in futures.items():
            try:
                raw[key].extend(future.result())
            except Exception as e:
                failed.append({"keyword": kw, "error": str(e)})

    # 카테고리별: 섹션 필터 → 사건 묶기 → 언론사 수로 순위
    used_links, used_reps = set(), []
    all_clusters = []   # (cluster, category) — 톱뉴스 선정용
    categories = []
    for cat in CATEGORIES:
        terms = cat.get("title_terms")
        seen, articles = set(), []
        for item in raw[cat["key"]]:
            art = normalize(item, since)
            if not art or art["sid"] not in cat["sids"] or art["link"] in seen:
                continue
            if terms and not any(t in art["title"] for t in terms):
                continue
            seen.add(art["link"])
            articles.append(art)

        clusters = cluster(articles)
        clusters.sort(key=lambda c: (len(c["sources"]), c["count"], c["rep"]["published"]),
                      reverse=True)

        picked = []
        for c in clusters:
            # 앞 카테고리에서 이미 고른 사건이면 건너뜀
            if c["rep"]["link"] in used_links or any(
                    same_cluster(u, c["related"]) for u in used_reps):
                continue
            used_links.add(c["rep"]["link"])
            used_reps.extend(c["related"][:5])
            all_clusters.append((c, cat))
            picked.append(to_output(c, cat))
            if len(picked) >= top_n:
                break

        categories.append({"key": cat["key"], "name": cat["name"],
                           "candidates": len(articles), "articles": picked})

    if not all_clusters:
        raise RuntimeError(f"수집된 기사 없음: {failed[:3]}")

    # 오늘의 톱뉴스: 전체에서 가장 많은 언론사가 다룬 사건
    top_cluster, top_cat = max(
        all_clusters, key=lambda x: (len(x[0]["sources"]), x[0]["count"], x[0]["rep"]["published"]))
    top_news = to_output(top_cluster, top_cat)
    for cat in categories:  # 카테고리 목록에서는 빼서 중복 방송 방지
        cat["articles"] = [a for a in cat["articles"] if a["link"] != top_news["link"]]

    # 본문 수집
    events = [top_news] + [a for cat in categories for a in cat["articles"]]
    if skip_body:
        for ev in events:
            ev["sources"] = ev["sources"][:SOURCES_PER_EVENT]
            ev["has_body"] = False
    else:
        attach_bodies(events, failed)

    result = {
        "collected_at": now.isoformat(),
        "top_news": top_news,
        "categories": categories,
        "failed": failed,
    }

    # 저장: BUCKET이 있으면 S3에 저장하고 위치만 반환 (Step Functions 256KB 한도 대비)
    bucket = os.environ.get("BUCKET")
    if not bucket:
        return result

    import boto3  # Lambda 기본 포함
    key = f"news/{now:%Y/%m/%d}/collected.json"
    boto3.client("s3").put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    return {
        "collected_at": result["collected_at"],
        "bucket": bucket,
        "s3_key": key,
        "top_news": top_news["title"],
        "events": len(events),
        "with_body": sum(ev["has_body"] for ev in events),
        "failed": len(failed),
    }


if __name__ == "__main__":
    # 로컬 테스트: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 환경 변수 설정 후
    #   python lambda_function.py
    print(json.dumps(lambda_handler({}, None), ensure_ascii=False, indent=2))