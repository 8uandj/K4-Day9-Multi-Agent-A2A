"""A0 - planning, dispatch, confidence rubric.

OWNER: Thanh vien 1 (Decision & Control)

Owns the case blackboard and decides which agent to re-run after a verifier failure.
"""

from __future__ import annotations

from ec_dispute.agents.base import Agent
from ec_dispute.contracts import CaseEnvelopePayload, CaseInput


class CoordinatorAgent(Agent):
    """A0 blackboard owner: creates T1 and routes verifier failures."""

    name = "A0_coordinator"

    def create_case_envelope(self, case: CaseInput):
        payload = CaseEnvelopePayload(
            case_id=case.case_id,
            claimed_order_id=case.customer_request.claimed_order_id,
            investigation_scope=case.investigation_scope,
            policy_version=case.policy_version,
        )
        return self.emit(
            case_id=case.case_id,
            to_agent="A1_order_product",
            stage="T1",
            payload_type="case_envelope",
            payload=payload,
            provenance=[],
            tool_calls=["parse_case_input"],
        )
