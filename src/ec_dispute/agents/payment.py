"""A3 - payment reconciliation.

OWNER: Thanh vien 3 (Analysis)

Has no order_items access on purpose: item totals must come from A1's artifact.
"""

from __future__ import annotations

from ec_dispute.agents.base import Agent
from ec_dispute.contracts import A2AEnvelope, OrderFacts, utc_now_z, build_envelope_id, PaymentReconciliation
from ec_dispute.tools.calculations import build_payment_reconciliation


class PaymentAgent(Agent):
    """Payment agent using deterministic fallback without LLM."""
    name = "A3_payment"
    allowed_tools = ()

    def __init__(self, data_store):
        self.data_store = data_store

    def emit(self, env: A2AEnvelope) -> A2AEnvelope:
        if env.payload_type != "order_facts":
            raise ValueError("Payment agent requires order_facts payload")
            
        facts: OrderFacts = env.payload
        payment_rows = self.data_store.payments_for(facts.order_id)
        
        recon = build_payment_reconciliation(facts, payment_rows)
        
        # Build provenance
        provenance = list(env.provenance)
        for payment in payment_rows:
            seq = payment.get("payment_sequential")
            if seq is not None:
                provenance.append(f"payment:{facts.order_id}:{seq}")
                
        return A2AEnvelope(
            envelope_id=build_envelope_id(env.case_id, "T3", self.name),
            case_id=env.case_id,
            from_agent=self.name,
            to_agent="A5_policy",
            stage="T3",
            produced_at=utc_now_z(),
            payload_type="payment_reconciliation",
            payload=recon,
            provenance=provenance,
            tool_calls=["build_payment_reconciliation"],
            self_check={"nulls_handled": True, "rounding_applied": True, "schema_validated": True},
            model="deterministic"
        )
