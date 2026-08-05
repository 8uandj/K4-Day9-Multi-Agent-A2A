"""EC_POLICY_V2 adjudication - produces the Verdict.

OWNER: Thanh vien 1 (Decision & Control)

Reads only artifacts, never CSVs. The decision table itself is frozen in
``contracts.output_schema.POLICY_RULES``; this module applies it in precedence order
and assembles secondary issues, parties, refund and actions.
"""

from __future__ import annotations

from ec_dispute.contracts import CustomerContext, DeliveryAnalysis, OrderFacts, PaymentReconciliation, Verdict


def decide(
    facts: OrderFacts,
    customer: CustomerContext,
    payment: PaymentReconciliation,
    delivery: DeliveryAnalysis,
) -> Verdict:
    """Apply PRIMARY_ISSUE_PRECEDENCE, then build the rest of the verdict around it."""
    raise NotImplementedError("TODO(TV1)")
