"""
DawnAir - save_briefing
write_script 결과(방송 대본 JSON)를 저장한다.
  S3       : scripts/{YYYY}/{MM}/{DD}/script.json   대본 전문 (웹앱 재생·다시보기용)
  DynamoDB : DawnAirBriefing 테이블, date(PK)        목록·메타데이터 빠른 조회용

입력: write_script의 반환값 그대로 (Step Functions에서 바로 이어받음)
환경 변수: BUCKET, TABLE(기본 DawnAirBriefing)
Lambda 설정: Python 3.12 / 타임아웃 30초 / 계층 없음
권한: s3:PutObject, dynamodb:PutItem
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


def lambda_handler(event, context):
    script = event
    y, m, d = script["date"].split("-")
    key = f"scripts/{y}/{m}/{d}/script.json"

    # 1) S3: 대본 전문
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(script, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )

    # 2) DynamoDB: 웹앱 첫 화면·히스토리 목록에 필요한 것만
    item = {
        "date": script["date"],
        "date_label": script["date_label"],
        "title": script["title"],
        "duration": script["duration_estimate"],          # 초 단위 (추정치)
        "scriptKey": key,                                  # 전문은 S3에서
        "headlines": [
            {"id": s["id"], "category": s["category"], "headline": s["headline"]}
            for s in script["segments"]
        ],
        "weatherSummary": {                                # 지역 key → 한 줄 요약
            k: {"name": v["name"], "summary": v["summary"], "outfit": v["outfit"],
                "temp_min": v["temp_min"], "temp_max": v["temp_max"]}
            for k, v in script["weather"].items()
        },
        "segmentCount": len(script["segments"]),
        "model": script.get("model"),
        "generatedAt": script["generated_at"],
        "savedAt": datetime.now(KST).isoformat(),
    }
    # DynamoDB는 float를 받지 못하므로 소수는 Decimal로 변환
    item = json.loads(json.dumps(item, ensure_ascii=False), parse_float=Decimal)
    table.put_item(Item=item)  # 같은 날짜로 다시 돌리면 덮어씀

    print(f"저장 완료: s3://{BUCKET}/{key}, {TABLE}[{script['date']}]")
    return {"date": script["date"], "bucket": BUCKET, "s3_key": key, "title": script["title"]}