import boto3

CANDIDATES = [
    ("us-east-1", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
    ("us-west-2", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
    ("us-east-1", "us.amazon.nova-micro-v1:0"),
    ("us-east-1", "us.amazon.nova-lite-v1:0"),
]

def lambda_handler(event, context):
    results = []
    for region, model in CANDIDATES:
        try:
            resp = boto3.client("bedrock-runtime", region_name=region).converse(
                modelId=model,
                messages=[{"role": "user", "content": [{"text": "안녕이라고만 답해줘"}]}],
                inferenceConfig={"maxTokens": 20},
            )
            results.append(f"✅ {region} {model}: {resp['output']['message']['content'][0]['text']}")
        except Exception as e:
            results.append(f"❌ {region} {model}: {type(e).__name__} {str(e)[:120]}")
    return results