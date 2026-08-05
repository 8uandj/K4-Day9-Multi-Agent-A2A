"""Shared agent runtime: prompt, tools, envelope emission.

OWNER: Thanh vien 1 (Decision & Control)

Each agent gets exactly the tools its row in the access matrix allows. Anything not
granted here is unreachable, which is what makes 'do not invent data' structural.
"""

from __future__ import annotations

from typing import Any

from ec_dispute.config import MODEL_BY_AGENT
from ec_dispute.contracts import A2AEnvelope, AgentName, PayloadType, SelfCheck, Stage, build_envelope_id, utc_now_z


class Agent:
    name: AgentName
    allowed_tools: tuple[str, ...] = ()

    @property
    def model_name(self) -> str:
        return MODEL_BY_AGENT[self.name].model

    def emit(
        self,
        *,
        case_id: str,
        to_agent: AgentName,
        stage: Stage,
        payload_type: PayloadType,
        payload: Any,
        provenance: list[str] | None = None,
        tool_calls: list[str] | None = None,
        self_check: SelfCheck | None = None,
        attempt: int = 0,
    ) -> A2AEnvelope:
        return A2AEnvelope(
            envelope_id=build_envelope_id(case_id, stage, self.name, attempt),
            case_id=case_id,
            from_agent=self.name,
            to_agent=to_agent,
            stage=stage,
            produced_at=utc_now_z(),
            payload_type=payload_type,
            payload=payload,
            provenance=provenance or [],
            tool_calls=tool_calls or [],
            self_check=self_check or SelfCheck(schema_validated=True),
            model=self.model_name,
        )
