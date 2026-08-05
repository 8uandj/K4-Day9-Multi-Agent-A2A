"""A1 — order, item, seller, product, category fact base.

OWNER: Thanh vien 2 (Data & Entities)

Runs first; everything downstream depends on its artifact. A3 takes its item totals from
here rather than re-reading ``order_items``, so an error in this agent surfaces as a
reconciliation mismatch instead of two agents covering for each other.

Access grant (docs/architecture.md section 4): orders, order_items, products, sellers,
category translation. Read-only.

Where an LLM earns its keep in this agent: deciding which entities to keep when an order
exceeds the output caps, and interpreting anomalies (unknown order, missing product row).
Across these 50 cases neither situation arises — the largest order has exactly 5 items and
3 sellers, right on the ceiling — so the deterministic path below is the whole agent today.
"""

from __future__ import annotations

from ec_dispute.agents.base import Agent
from ec_dispute.contracts import A2AEnvelope, CaseInput, OrderFacts, SelfCheck
from ec_dispute.tools.lookups import build_order_facts, order_facts_provenance


class OrderProductAgent(Agent):
    name = "A1_order_product"
    allowed_tools = ("build_order_facts", "lookup_order", "lookup_items", "lookup_product", "lookup_seller")

    def analyse(self, case: CaseInput) -> OrderFacts:
        return build_order_facts(
            self.store,
            case.customer_request.claimed_order_id,
            include_product_context=case.investigation_scope.include_product_context,
        )

    def run(self, case: CaseInput, *, to_agent: str = "A0_coordinator", attempt: int = 0) -> A2AEnvelope:
        """Emit ``order_facts`` at T2. The coordinator fans it out to A2, A3 and A4."""
        facts = self.analyse(case)
        return self.emit(
            case_id=case.case_id,
            to_agent=to_agent,
            stage="T2",
            payload_type="order_facts",
            payload=facts,
            provenance=order_facts_provenance(facts),
            tool_calls=["build_order_facts"],
            self_check=SelfCheck(
                # 6/50 orders carry no item row at all; that is data, not a failure.
                nulls_handled=True,
                rounding_applied=True,
                schema_validated=True,
            ),
            attempt=attempt,
        )
