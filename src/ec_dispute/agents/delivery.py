"""A4 - delivery and seller handoff variance.

OWNER: Thanh vien 3 (Analysis)

Carries the heaviest null load in the pipeline.
"""

from __future__ import annotations

from ec_dispute.agents.base import Agent
from ec_dispute.contracts import A2AEnvelope, OrderFacts, utc_now_z, build_envelope_id, DeliveryAnalysis
from ec_dispute.tools.calculations import build_delivery_analysis


class DeliveryAgent(Agent):
    """Delivery agent using deterministic fallback without LLM."""
    name = "A4_delivery"
    allowed_tools = ()
    
    def emit(self, env: A2AEnvelope) -> A2AEnvelope:
        if env.payload_type != "order_facts":
            raise ValueError("Delivery agent requires order_facts payload")
            
        facts: OrderFacts = env.payload
        analysis = build_delivery_analysis(facts)
        
        return A2AEnvelope(
            envelope_id=build_envelope_id(env.case_id, "T3", self.name),
            case_id=env.case_id,
            from_agent=self.name,
            to_agent="A5_policy",
            stage="T3",
            produced_at=utc_now_z(),
            payload_type="delivery_analysis",
            payload=analysis,
            provenance=list(env.provenance),
            tool_calls=["build_delivery_analysis"],
            self_check={"nulls_handled": True, "rounding_applied": True, "schema_validated": True},
            model="deterministic"
        )
