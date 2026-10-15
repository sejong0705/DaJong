"""
DawnAir - user (사용자 등록 · 조회 API)
브라우저(기기)마다 프론트가 만든 UUID(deviceId)를 사용자 ID로 쓴다. 비밀번호 없음.
기기를 바꾸거나 브라우저 데이터를 지우면 새 사용자로 등록된다 (의도된 동작).
Lambda 함수 URL로 열어서 프론트가 fetch로 호출한다.

  POST {URL}                     사용자 등록 / 닉네임 변경
       body: {"deviceId": "<uuid>", "nickname": "닉네임"}
       → 200 {"user": {...}}
  GET  {URL}?deviceId=<uuid>     사용자 조회 (앱을 열 때마다 호출, 마지막 접속 시간 갱신)
       → 200 {"user": {...}} / 없으면 404

DynamoDB 항목 (테이블 sgu-20260918-DawnAirUser, 파티션 키 deviceId:String)
  deviceId, nickname, userAgent, createdAt, updatedAt, lastSeenAt
  나중에 취향 설정 등은 이 항목에 속성을 추가하면 된다.

환경 변수: TABLE(기본 sgu-20260918-DawnAirUser)
Lambda 설정: Python 3.12 / 타임아웃 10초 / 계층 없음
권한: dynamodb:GetItem, dynamodb:UpdateItem
함수 URL: 인증 NONE, CORS 는 함수 URL 설정에서 켠다 (코드에서 CORS 헤더를 넣지 않음)
  Allow origin: https://main.d1onq2byujgijj.amplifyapp.com, http://localhost:5173
  Allow methods: GET, POST / Allow headers: content-type
"""
import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone

import boto3

KST = timezone(timedelta(hours=9))
TABLE = os.environ.get("TABLE", "sgu-20260918-DawnAirUser")
NICKNAME_MAX = 20

table = boto3.resource("dynamodb").Table(TABLE)

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-store",  # 사용자 정보는 캐시하지 않음
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def now():
    return datetime.now(KST).isoformat()


def valid_device_id(v):
    return isinstance(v, str) and UUID_RE.match(v.lower()) is not None


def clean_nickname(v):
    """앞뒤 공백·제어문자 제거, 1~20자. 올바르지 않으면 None"""
    if not isinstance(v, str):
        return None
    v = CONTROL_RE.sub("", v).strip()
    return v if 1 <= len(v) <= NICKNAME_MAX else None


def read_body(event):
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError:
        return None


def register(event):
    data = read_body(event)
    if data is None:
        return respond(400, {"error": "JSON 형식이 아닙니다."})

    device_id = data.get("deviceId")
    nickname = clean_nickname(data.get("nickname"))
    if not valid_device_id(device_id):
        return respond(400, {"error": "deviceId 가 올바르지 않습니다."})
    if not nickname:
        return respond(400, {"error": f"닉네임은 1~{NICKNAME_MAX}자로 입력해 주세요."})

    t = now()
    user_agent = ((event.get("headers") or {}).get("user-agent") or "")[:300]
    # 처음이면 생성, 이미 있으면 닉네임만 바꿈 (createdAt 은 처음 값 유지)
    r = table.update_item(
        Key={"deviceId": device_id.lower()},
        UpdateExpression=(
            "SET #n = :n, #ua = :ua, #u = :t, #s = :t, #c = if_not_exists(#c, :t)"
        ),
        ExpressionAttributeNames={
            "#n": "nickname", "#ua": "userAgent", "#u": "updatedAt",
            "#s": "lastSeenAt", "#c": "createdAt",
        },
        ExpressionAttributeValues={":n": nickname, ":ua": user_agent, ":t": t},
        ReturnValues="ALL_NEW",
    )
    return respond(200, {"user": r["Attributes"]})


def get_user(event):
    q = event.get("queryStringParameters") or {}
    device_id = q.get("deviceId")
    if not valid_device_id(device_id):
        return respond(400, {"error": "deviceId 가 올바르지 않습니다."})

    # 있으면 마지막 접속 시간만 갱신, 없으면 404 (새로 만들지 않음)
    try:
        r = table.update_item(
            Key={"deviceId": device_id.lower()},
            UpdateExpression="SET #s = :t",
            ConditionExpression="attribute_exists(#id)",
            ExpressionAttributeNames={"#s": "lastSeenAt", "#id": "deviceId"},
            ExpressionAttributeValues={":t": now()},
            ReturnValues="ALL_NEW",
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return respond(404, {"error": "등록되지 않은 기기입니다."})
    return respond(200, {"user": r["Attributes"]})


def lambda_handler(event, context):
    event = event or {}
    method = (event.get("requestContext", {}).get("http", {}).get("method") or "GET").upper()

    if method == "POST":
        return register(event)
    if method == "GET":
        return get_user(event)
    return respond(405, {"error": "지원하지 않는 요청입니다."})
