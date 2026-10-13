import os
from openai import OpenAI

client = OpenAI(
    base_url=os.environ["LLM_BASE_URL"],   # https://<게이트웨이 주소>
    api_key=os.environ["LLM_API_KEY"],     # sk-...
)

r = client.chat.completions.create(
    model="bedrock-haiku",
    messages=[
        {"role": "system", "content": "너는 간결하게 답하는 도우미다."},
        {"role": "user", "content": "파이썬 리스트 컴프리헨션 한 줄로 설명해줘"},
    ],
)
print(r.choices[0].message.content)

