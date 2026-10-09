"""
DawnAir - tts_briefing (Polly 음성 합성)
write_script 결과(대본 JSON)를 받아 지역별 방송 mp3를 만들고 S3에 저장한 뒤,
대본에 음성 정보(audio)를 붙여 다음 단계(save_briefing)로 넘긴다.

동작
  1) 재생 순서대로 파트를 만든다: 오프닝 → 날씨(지역별) → 뉴스 꼭지 → 클로징
  2) 파트마다 Polly SynthesizeSpeech 호출 (한 번에 3,000자 제한이라 파트별로 나눔)
     - 날씨를 뺀 파트는 모든 지역이 같으니 한 번만 합성해서 재사용
     - 파트 끝에 0.7초 쉼(SSML break)을 넣어 코너가 넘어가는 느낌을 줌
  3) 지역별로 mp3 조각을 이어 붙여 audio/YYYY/MM/DD/briefing-{지역}.mp3 로 저장
  4) mp3 프레임을 세서 파트별 실제 시작 시간(챕터)과 전체 길이를 계산

입력: write_script 반환값 그대로
출력: 입력 + "audio": {지역: {"key", "duration", "chapters": [{"key", "start"}]}}
환경 변수: BUCKET, VOICE_ID(기본 Seoyeon), POLLY_REGION(기본 ap-northeast-2)
Lambda 설정: Python 3.12+ / 타임아웃 2분 / 메모리 256MB / 계층 없음
권한: polly:SynthesizeSpeech, s3:PutObject
"""
import html
import os
import re

import boto3

BUCKET = os.environ["BUCKET"]
VOICE_ID = os.environ.get("VOICE_ID", "Seoyeon")
PAUSE_MS = 700        # 코너 사이 쉼
MAX_CHARS = 2500      # Polly 한 번에 3,000자 제한보다 여유 있게

# 발음 교정 사전: 대본에 이 단어가 나오면 오른쪽처럼 읽게 함 (SSML sub)
PRONOUNCE = {
    # "LH": "엘에이치",
}

polly = boto3.client("polly", region_name=os.environ.get("POLLY_REGION", "ap-northeast-2"))
s3 = boto3.client("s3")


# ---------------------------------------------------------------- 합성
def to_ssml(text, pause_ms):
    t = html.escape(text, quote=False)
    for word, alias in PRONOUNCE.items():
        w = html.escape(word, quote=False)
        t = t.replace(w, f'<sub alias="{html.escape(alias)}">{w}</sub>')
    pause = f'<break time="{pause_ms}ms"/>' if pause_ms else ""
    return f"<speak>{t}{pause}</speak>"


def chunks(text):
    """MAX_CHARS 보다 긴 파트는 문장 단위로 나눈다 (보통은 한 덩어리)."""
    out, cur = [], ""
    for s in re.split(r"(?<=[.!?])\s+", text.strip()):
        if cur and len(cur) + len(s) + 1 > MAX_CHARS:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    return out + ([cur] if cur else [])


def synth(text, pause_ms):
    pieces = chunks(text)
    audio = b""
    for i, piece in enumerate(pieces):
        r = polly.synthesize_speech(
            Engine="neural",
            VoiceId=VOICE_ID,
            LanguageCode="ko-KR",
            OutputFormat="mp3",
            SampleRate="24000",
            TextType="ssml",
            Text=to_ssml(piece, pause_ms if i == len(pieces) - 1 else 0),
        )
        audio += r["AudioStream"].read()
    return audio


# ---------------------------------------------------------------- mp3 길이 계산
# mp3는 일정 길이의 프레임이 이어진 구조라, 프레임 수 × 프레임당 시간 = 재생 시간
_BITRATE = {3: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],      # MPEG-1
            2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}          # MPEG-2 / 2.5
_RATE = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def mp3_duration(data):
    i, n, total = 0, len(data), 0.0
    if data[:3] == b"ID3":  # 앞에 태그가 있으면 건너뜀
        i = 10 + ((data[6] & 0x7F) << 21 | (data[7] & 0x7F) << 14 | (data[8] & 0x7F) << 7 | (data[9] & 0x7F))
    while i + 4 <= n:
        b1, b2 = data[i + 1], data[i + 2]
        ver, layer = (b1 >> 3) & 3, (b1 >> 1) & 3
        br_i, sr_i, pad = (b2 >> 4) & 15, (b2 >> 2) & 3, (b2 >> 1) & 1
        if data[i] != 0xFF or (b1 & 0xE0) != 0xE0 or ver == 1 or layer != 1 or br_i in (0, 15) or sr_i == 3:
            i += 1
            continue
        rate = _RATE[ver][sr_i]
        bitrate = _BITRATE[3 if ver == 3 else 2][br_i] * 1000
        samples = 1152 if ver == 3 else 576
        total += samples / rate
        i += (samples // 8) * bitrate // rate + pad
    return total


# ---------------------------------------------------------------- 핸들러
def lambda_handler(event, context):
    script = event
    y, m, d = script["date"].split("-")

    common = [("opening", script["opening"]["speech"])]
    common_tail = [(s["id"], s["speech"]) for s in script["segments"]]
    common_tail.append(("closing", script["closing"]["speech"]))

    # 지역과 상관없는 파트는 한 번만 합성
    cache = {}
    for key, text in common + common_tail:
        cache[key] = synth(text, 0 if key == "closing" else PAUSE_MS)
    calls = len(cache)

    audio = {}
    for region, w in script["weather"].items():
        parts = common + [("weather", w["speech"])] + common_tail
        weather_mp3 = synth(w["speech"], PAUSE_MS)
        calls += 1

        data, chapters, t = b"", [], 0.0
        for key, _ in parts:
            piece = weather_mp3 if key == "weather" else cache[key]
            chapters.append({"key": key, "start": round(t, 2)})
            t += mp3_duration(piece)
            data += piece

        k = f"audio/{y}/{m}/{d}/briefing-{region}.mp3"
        s3.put_object(Bucket=BUCKET, Key=k, Body=data, ContentType="audio/mpeg")
        audio[region] = {"key": k, "duration": round(t, 1), "chapters": chapters}
        print(f"{region}: {round(t)}초, {len(data) // 1024}KB → s3://{BUCKET}/{k}")

    print(f"Polly 호출 {calls}회")
    return {**script, "audio": audio}