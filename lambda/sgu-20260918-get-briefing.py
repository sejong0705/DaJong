"""
DawnAir - get_briefing (웹앱 조회 API)
Lambda 함수 URL로 열어서 프론트가 fetch로 호출한다.

  GET {URL}                    오늘 방송 (아직 없으면 가장 최근 방송)
  GET {URL}?date=2026-10-09    특정 날짜 방송 (지난 방송 듣기)
  GET {URL}?list=1             히스토리 목록 (최신순)

응답: {"meta": DynamoDB 항목, "script": S3 대본 전문} / 목록은 {"items": [...]}
환경 변수: BUCKET, TABLE(기본 DawnAirBriefing)
Lambda 설정: Python 3.12 / 타임아웃 10초 / 계층 없음
권한: dynamodb:GetItem, dynamodb:Scan, s3:GetObject
"""
import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3

KST = timezone(timedelta(hours=9))
BUCKET = os.environ["BUCKET"]
TABLE = os.environ.get("TABLE", "DawnAirBriefing")

s3 = boto3.client("s3")
table = boto3.resource("dynamodb").Table(TABLE)


def to_json(o):
    """DynamoDB 숫자(Decimal) → JSON 숫자"""
    if isinstance(o, Decimal):
        return int(o) if o % 1 == 0 else float(o)
    raise TypeError(type(o))


def respond(status, body, cache=60):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": f"public, max-age={cache}",
        },
        "body": json.dumps(body, ensure_ascii=False, default=to_json),
    }


def list_briefings():
    """히스토리 목록. 하루 1건이라 전체를 읽어 날짜순 정렬해도 충분히 작다."""
    kwargs = {
        "ProjectionExpression": "#d, #l, #t, #dur, #c",
        "ExpressionAttributeNames": {"#d": "date", "#l": "date_label", "#t": "title",
                                     "#dur": "duration", "#c": "segmentCount"},
    }
    items = []
    while True:
        r = table.scan(**kwargs)
        items += r["Items"]
        if "LastEvaluatedKey" not in r:
            break
        kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]
    return sorted(items, key=lambda x: x["date"], reverse=True)


def get_briefing(date):
    meta = table.get_item(Key={"date": date}).get("Item")
    if not meta:
        return None
    obj = s3.get_object(Bucket=BUCKET, Key=meta["scriptKey"])
    return {"meta": meta, "script": json.loads(obj["Body"].read())}


def lambda_handler(event, context):
    q = (event or {}).get("queryStringParameters") or {}

    if q.get("list"):
        return respond(200, {"items": list_briefings()})

    if q.get("date"):
        b = get_briefing(q["date"])
        if not b:
            return respond(404, {"error": f"{q['date']} 방송이 없습니다."})
        return respond(200, b, cache=86400)  # 지난 방송은 바뀌지 않음

    # 기본: 오늘 방송. 아직 없으면(새벽 생성 전) 가장 최근 방송
    b = get_briefing(datetime.now(KST).strftime("%Y-%m-%d"))
    if not b:
        items = list_briefings()
        if not items:
            return respond(404, {"error": "아직 방송이 없습니다."})
        b = get_briefing(items[0]["date"])
    return respond(200, b, cache=300)