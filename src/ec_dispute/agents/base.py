"""Shared agent runtime: prompt, tools, envelope emission.

OWNER: Thanh vien 1 (Decision & Control)

Each agent gets exactly the tools its row in the access matrix allows. Anything not
granted here is unreachable, which is what makes 'do not invent data' structural.
"""

from __future__ import annotations

from ec_dispute.contracts import A2AEnvelope


class Agent:
    name: str
    allowed_tools: tuple[str, ...] = ()

    def emit(self, **kwargs) -> A2AEnvelope:
        raise NotImplementedError("TODO(TV1)")
