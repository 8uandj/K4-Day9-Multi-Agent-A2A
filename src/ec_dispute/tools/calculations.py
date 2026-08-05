"""Deterministic money and time arithmetic for A3 and A4.

OWNER: Thanh vien 3 (Analysis)

Every number the grader reads is produced here. Two rules that cost the most points:
  - missing timestamp -> variance is None, and NEVER inferred as late (14/50 and 13/50 cases)
  - no item row -> expected/difference/reconciled are None, not 0.0 (6/50 cases)
"""

from __future__ import annotations

from ec_dispute.contracts import DeliveryAnalysis, OrderFacts, PaymentReconciliation


def build_payment_reconciliation(facts: OrderFacts, payment_rows: list[dict]) -> PaymentReconciliation:
    """A3. Item totals come from ``facts`` (handed over by A1), not from a second CSV read."""
    raise NotImplementedError("TODO(TV3)")


def build_delivery_analysis(facts: OrderFacts) -> DeliveryAnalysis:
    """A4. handoff variance compares carrier handoff against each seller's EARLIEST shipping limit."""
    raise NotImplementedError("TODO(TV3)")
