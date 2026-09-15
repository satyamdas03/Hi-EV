"""Quick probe: which NVIDIA NIM models return clean final answers for this key?"""

import asyncio

import httpx

from ev.config import get_settings

settings = get_settings()
key = settings.nvidia_api_key.get_secret_value() if settings.nvidia_api_key else None
base_url = settings.nvidia_base_url or "https://integrate.api.nvidia.com/v1"

CANDIDATES = [
    "google/gemma-3-12b-it",
    "google/gemma-3-4b-it",
    "meta/llama-3.2-11b-vision-instruct",
    "meta/llama-3.2-90b-vision-instruct",
    "mistralai/mistral-7b-instruct-v0.3",
    "mistralai/mistral-large",
    "nv-mistralai/mistral-nemo-12b-instruct",
    "nvidia/llama3-chatqa-1.5-70b",
    "nvidia/mistral-nemo-minitron-8b-8k-instruct",
    "nvidia/nemotron-3-super-120b-a12b",
    "openai/gpt-oss-20b",
    "poolside/laguna-xs-2.1",
    "zyphra/zamba2-7b-instruct",
    "aisingapore/sea-lion-7b-instruct",
    "databricks/dbrx-instruct",
    "ibm/granite-3.0-8b-instruct",
]


def clean(content: str | None, reasoning: str | None) -> str:
    return (content or reasoning or "").strip()


async def probe(client: httpx.AsyncClient, model: str) -> dict:
    try:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant. Answer concisely."},
                    {"role": "user", "content": "What is 2+2?"},
                ],
                "max_tokens": 40,
                "temperature": 0.2,
            },
            timeout=30,
        )
        body = resp.json()
        if resp.status_code != 200:
            return {"model": model, "status": resp.status_code, "error": body}
        msg = body["choices"][0]["message"]
        return {
            "model": model,
            "status": resp.status_code,
            "content": clean(msg.get("content"), msg.get("reasoning_content")),
        }
    except (httpx.HTTPError, httpx.InvalidJSONError, KeyError, ValueError) as exc:
        return {"model": model, "status": -1, "error": str(exc)}


async def main() -> None:
    if not key:
        print("EV_NVIDIA_API_KEY not set")
        return
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(limits=limits, timeout=30) as client:
        results = await asyncio.gather(*[probe(client, m) for m in CANDIDATES])

    working = [r for r in results if r.get("status") == 200]
    failing = [r for r in results if r.get("status") != 200]

    print("\n=== WORKING MODELS ===")
    for r in working:
        print(f"{r['model']}: {r['content'][:80]!r}")

    print("\n=== FAILING MODELS ===")
    for r in failing:
        err = r.get("error")
        if isinstance(err, dict):
            err = err.get("detail") or err.get("title") or str(err)
        print(f"{r['model']}: {r['status']} -> {err}")


if __name__ == "__main__":
    asyncio.run(main())
