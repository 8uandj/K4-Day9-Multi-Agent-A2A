"""OpenAI-compatible chat client (Ollama locally, any provider remotely).

OWNER: Thanh vien 1 (Decision & Control)

Switching between local Ollama and a hosted provider must be a base_url change only -
no code edits - so the team can trade latency for throughput mid-competition.
"""

from __future__ import annotations

from ec_dispute.config import ModelSpec


class LLMClient:
    def __init__(self, spec: ModelSpec) -> None:
        self.spec = spec

    async def complete_json(self, system: str, user: str, response_model: type) -> object:
        """Call the model and parse the reply into ``response_model``. Retries once on schema error."""
        raise NotImplementedError("TODO(TV1)")
