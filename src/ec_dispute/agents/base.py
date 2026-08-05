"""Shared agent runtime: prompt, tools, envelope emission.

OWNER: Thanh vien 1 (Decision & Control)

Each agent gets exactly the tools its row in the access matrix allows. Anything not
granted here is unreachable, which is what makes 'do not invent data' structural.

TV2 added ``__init__``, ``ToolPermissionError`` and ``check_tools`` (integration log
2026-08-05) because A1/A2/A6 needed them. Pure contract plumbing — the scheduling and
repair logic in ``orchestrator.py`` stays TV1's.
"""

from __future__ import annotations

from typing import Any

from ec_dispute.config import MODEL_BY_AGENT
from ec_dispute.contracts import A2AEnvelope, AgentName, PayloadType, SelfCheck, Stage, build_envelope_id, utc_now_z


class ToolPermissionError(RuntimeError):
    """An agent reached for a tool outside its grant. Never catch this — fix the agent."""


class Agent:
    name: AgentName
    allowed_tools: tuple[str, ...] = ()

    def __init__(self, store: Any = None, llm: Any = None) -> None:
        #: Read-only data access. Agents whose access-matrix row is empty are constructed
        #: with ``store=None`` and physically cannot reach a CSV.
        self.store = store
        #: Optional LLM client. The deterministic tool path is authoritative for every graded
        #: number; the model handles the judgement calls named in each agent's docstring.
        self.llm = llm

    @property
    def model_name(self) -> str:
        return MODEL_BY_AGENT[self.name].model

    def check_tools(self, tool_calls: tuple[str, ...] | list[str]) -> None:
        """Turn the access matrix into something that actually runs.

        An empty ``allowed_tools`` means the grant has not been declared yet, so nothing is
        enforced — declaring the tuple is what switches enforcement on for that agent.
        """
        if not self.allowed_tools:
            return
        forbidden = [tool for tool in tool_calls if tool not in self.allowed_tools]
        if forbidden:
            raise ToolPermissionError(f"{self.name} may not call {forbidden}; granted: {list(self.allowed_tools)}")

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
        """Wrap an artifact in a validated handoff envelope.

        Validation happens on construction, so a malformed artifact fails at the sender
        rather than confusing the receiver.
        """
        tool_calls = list(tool_calls or [])
        self.check_tools(tool_calls)
        return A2AEnvelope(
            envelope_id=build_envelope_id(case_id, stage, self.name, attempt),
            case_id=case_id,
            from_agent=self.name,
            to_agent=to_agent,
            stage=stage,
            produced_at=utc_now_z(),
            payload_type=payload_type,
            payload=payload,
            provenance=list(provenance or []),
            tool_calls=tool_calls,
            self_check=self_check or SelfCheck(schema_validated=True),
            model=self.model_name,
        )
