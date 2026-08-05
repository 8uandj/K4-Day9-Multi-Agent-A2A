"""Model registry and runtime configuration.

README section 9 requires model names to live in SOURCE CODE, not in ``.env``, and to be
mirrored into ``logging/metadata.json``. ``.env`` carries only secrets (API keys, base URLs).

Every model here is <= 10B parameters, per the lab constraint. A7 deliberately runs a
different model family from the agents it checks: a verifier that shares the producer's
blind spots does not verify anything.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - lets py_compile work before venv install
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()
else:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

FRAMEWORK = "custom asyncio orchestrator + Pydantic v2 (OpenAI-compatible client)"
RUNTIME = "Hosted OpenAI-compatible API (OpenRouter recommended)"
PARAMETER_CEILING_B = 10.0


@dataclass(frozen=True)
class ModelSpec:
    agent: str
    model: str
    parameters_b: float
    thinking: bool = False


MODEL_REGISTRY: tuple[ModelSpec, ...] = (
    ModelSpec("A0_coordinator", "qwen/qwen3-8b", 8.2, thinking=True),
    ModelSpec("A1_order_product", "qwen/qwen3-8b", 8.2),
    ModelSpec("A2_customer", "qwen/qwen3-8b", 8.2),
    ModelSpec("A3_payment", "qwen/qwen3-8b", 8.2),
    ModelSpec("A4_delivery", "qwen/qwen3-8b", 8.2),
    ModelSpec("A5_policy", "qwen/qwen3-8b", 8.2, thinking=True),
    ModelSpec("A6_evidence", "qwen/qwen3-8b", 8.2),
    ModelSpec("A7_verifier", "meta-llama/llama-3.1-8b-instruct", 8.0),
)

MODEL_BY_AGENT: dict[str, ModelSpec] = {spec.agent: spec for spec in MODEL_REGISTRY}

# OpenRouter free-tier fallback. It is useful for smoke tests and low-volume development
# when the paid account has no credits left. Free routing has low rate limits and the exact
# underlying model may change, so keep MODEL_REGISTRY above as the source of truth for final runs.
OPENROUTER_FREE_MODEL = "openrouter/free"
FALLBACK_MODEL_BY_AGENT: dict[str, str] = {spec.agent: OPENROUTER_FREE_MODEL for spec in MODEL_REGISTRY}

# Deterministic decoding: same input must produce the same output on a re-run.
GENERATION = {"temperature": 0.0, "top_p": 1.0, "seed": 42}


def base_url() -> str:
    return os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")


def api_key() -> str:
    return os.getenv("LLM_API_KEY", "ollama")


def assert_parameter_ceiling() -> None:
    """Fail loudly rather than submit a run that breaks the <=10B rule."""
    for spec in MODEL_REGISTRY:
        if spec.parameters_b > PARAMETER_CEILING_B:
            raise ValueError(f"{spec.agent} uses {spec.model} at {spec.parameters_b}B > {PARAMETER_CEILING_B}B")


POLICY_VERSION = "EC_POLICY_V2"

#: Deterministic tools the agents may call. Every graded number originates in one of these;
#: the models choose which tool to call and how to read the result, they never do the
#: arithmetic themselves. Declared here so metadata.json reports tools, models and policy
#: version from a single source instead of three hand-maintained lists.
TOOLS: tuple[dict[str, str], ...] = (
    {"name": "build_order_facts", "agent": "A1_order_product", "module": "ec_dispute.tools.lookups"},
    {"name": "build_customer_context", "agent": "A2_customer", "module": "ec_dispute.tools.lookups"},
    {"name": "build_payment_reconciliation", "agent": "A3_payment", "module": "ec_dispute.tools.calculations"},
    {"name": "build_delivery_analysis", "agent": "A4_delivery", "module": "ec_dispute.tools.calculations"},
    {"name": "apply_policy", "agent": "A5_policy", "module": "ec_dispute.policy_engine"},
    {"name": "assemble_output", "agent": "A6_evidence", "module": "ec_dispute.agents.evidence"},
    {"name": "verify_candidate", "agent": "A7_verifier", "module": "ec_dispute.verifier"},
    {"name": "key_exists", "agent": "A7_verifier", "module": "ec_dispute.data_store"},
)


def metadata_document() -> dict:
    assert_parameter_ceiling()
    return {
        "policy_version": POLICY_VERSION,
        "framework": FRAMEWORK,
        "runtime": RUNTIME,
        "generation": GENERATION,
        "models": [asdict(spec) for spec in MODEL_REGISTRY],
        "tools": [dict(tool) for tool in TOOLS],
        "fallback_models": FALLBACK_MODEL_BY_AGENT,
        "max_parameters_b": max(spec.parameters_b for spec in MODEL_REGISTRY),
        "constraint": f"<={PARAMETER_CEILING_B}B per agent - satisfied",
    }
