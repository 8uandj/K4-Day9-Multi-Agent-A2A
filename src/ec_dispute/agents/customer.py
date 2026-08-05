"""A2 — identity resolution and order history.

OWNER: Thanh vien 2 (Data & Entities)

Sees only the ``order_id`` / ``customer_id`` columns plus the customers table, so it cannot
form an opinion about delivery or money even if a prompt tried to talk it into one.

Two outputs matter downstream: the ``repeat_customer`` signal for A5's secondary issues
(26/50 cases), and ``related_order_ids`` — which README section 3 confines to
``customer_context`` and bars from ``affected_entities``.
"""

from __future__ import annotations

from ec_dispute.agents.base import Agent
from ec_dispute.contracts import A2AEnvelope, CaseInput, CustomerContext, OrderFacts, SelfCheck
from ec_dispute.tools.lookups import build_customer_context, customer_context_provenance


class CustomerAgent(Agent):
    name = "A2_customer"
    allowed_tools = ("build_customer_context", "lookup_customer", "lookup_customer_orders")

    def analyse(self, case: CaseInput, facts: OrderFacts) -> CustomerContext:
        """``facts.customer_id`` arrives by handoff from A1 — A2 never reads the orders table itself."""
        if not facts.customer_id:
            return CustomerContext(customer_unique_id=None, related_order_ids=[])
        return build_customer_context(
            self.store,
            facts.customer_id,
            facts.order_id,
            include_history=case.investigation_scope.include_customer_history,
        )

    def run(
        self,
        case: CaseInput,
        facts: OrderFacts,
        *,
        to_agent: str = "A0_coordinator",
        attempt: int = 0,
    ) -> A2AEnvelope:
        """Emit ``customer_context`` at T3."""
        context = self.analyse(case, facts)
        provenance = customer_context_provenance(facts.customer_id, context) if facts.customer_id else []
        return self.emit(
            case_id=case.case_id,
            to_agent=to_agent,
            stage="T3",
            payload_type="customer_context",
            payload=context,
            provenance=provenance,
            tool_calls=["build_customer_context"],
            self_check=SelfCheck(nulls_handled=True, rounding_applied=True, schema_validated=True),
            attempt=attempt,
        )

    @staticmethod
    def is_repeat_customer(context: CustomerContext) -> bool:
        """Signal for A5's ``repeat_customer`` secondary issue."""
        return bool(context.related_order_ids)
