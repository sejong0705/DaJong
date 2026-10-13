import os
import json
from openai import OpenAI

client = OpenAI(
    base_url=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
)

def lambda_handler(event, context):
    prompt = event.get("prompt", "안녕이라고만 답해")
    model = event.get("model", "bedrock-haiku")

    r = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "너는 간결하게 답하는 도우미다."},
            {"role": "user", "content": prompt},
        ],
    )
    answer = r.choices[0].message.content

    return {
        "statusCode": 200,
        "body": json.dumps({"answer": answer}, ensure_ascii=False),
    }