"""Smoke-test the configured OpenAI-compatible LLM API without printing secrets."""

from __future__ import annotations

import argparse
import asyncio

from pydantic import BaseModel

from ec_dispute.config import MODEL_BY_AGENT, api_key, base_url
from ec_dispute.llm_client import LLMClient


class SmokeResponse(BaseModel):
    ok: bool
    provider: str


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test LLM_BASE_URL/LLM_API_KEY against one configured agent model.")
    parser.add_argument("--agent", default="A0_coordinator", choices=sorted(MODEL_BY_AGENT))
    args = parser.parse_args()

    if not api_key():
        raise SystemExit("LLM_API_KEY is empty. Put it in .env first.")

    spec = MODEL_BY_AGENT[args.agent]
    client = LLMClient(spec)
    response = await client.complete_json(
        system="Return only JSON.",
        user='Return exactly {"ok": true, "provider": "api"}.',
        response_model=SmokeResponse,
    )

    print(f"base_url={base_url()}")
    print(f"agent={args.agent}")
    print(f"model={spec.model}")
    print(f"response={response.model_dump()}")


if __name__ == "__main__":
    asyncio.run(main())
