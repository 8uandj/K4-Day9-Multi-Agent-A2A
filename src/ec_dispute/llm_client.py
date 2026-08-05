"""OpenAI-compatible chat client (Ollama locally, any provider remotely).

OWNER: Thanh vien 1 (Decision & Control)

Switching between local Ollama and a hosted provider must be a base_url change only -
no code edits - so the team can trade latency for throughput mid-competition.
"""

from __future__ import annotations

import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from ec_dispute.config import GENERATION, api_key, base_url
from ec_dispute.config import ModelSpec


class LLMClient:
    def __init__(self, spec: ModelSpec) -> None:
        self.spec = spec

    async def complete_json(self, system: str, user: str, response_model: type) -> object:
        """Call the model and parse the reply into ``response_model``. Retries once on schema error."""
        last_error: Exception | None = None
        retry_hint = ""
        for _ in range(2):
            try:
                content = await asyncio.to_thread(self._chat_completion, system, user + retry_hint, response_model)
                return self._parse_response(content, response_model)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                retry_hint = (
                    "\n\nYour previous response did not match the required JSON schema. "
                    f"Return only valid JSON for {response_model.__name__}. Error: {exc}"
                )
        raise ValueError(f"{self.spec.agent} failed to return valid {response_model.__name__}") from last_error

    def _chat_completion(self, system: str, user: str, response_model: type) -> str:
        payload = {
            "model": self.spec.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **GENERATION,
            "response_format": {"type": "json_object"},
        }
        if hasattr(response_model, "model_json_schema"):
            payload["messages"][0]["content"] += (
                "\nReturn JSON matching this schema:\n"
                + json.dumps(response_model.model_json_schema(), ensure_ascii=False)
            )

        endpoint = base_url().rstrip("/") + "/chat/completions"
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key()}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc.reason}") from exc
        return body["choices"][0]["message"]["content"]

    @staticmethod
    def _parse_response(content: str, response_model: type) -> object:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            payload = json.loads(content[start : end + 1])
        if hasattr(response_model, "model_validate"):
            return response_model.model_validate(payload)
        return payload
