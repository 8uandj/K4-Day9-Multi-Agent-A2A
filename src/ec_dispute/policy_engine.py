"""EC_POLICY_V2 adjudication - produces the Verdict.

OWNER: Thanh vien 1 (Decision & Control)

Reads only artifacts, never CSVs. The decision table itself is frozen in
``contracts.output_schema.POLICY_RULES``; this module applies it in precedence order
and assembles secondary issues, parties, refund and actions.
"""

from __future__ import annotations

from ec_dispute.contracts import (
    POLICY_RULES,
    CaseAssessment,
    CustomerContext,
    DeliveryAnalysis,
    FinancialResolution,
    OrderFacts,
    PaymentReconciliation,
    PrimaryIssue,
    RankedCause,
    ResponsibleParty,
    RootCauseAnalysis,
    Verdict,
)


def _is_paid(payment: PaymentReconciliation) -> bool:
    return payment.payment_total_brl > 0


def _is_late_delivery(delivery: DeliveryAnalysis) -> bool:
    return delivery.delivery_variance_hours is not None and delivery.delivery_variance_hours > 0


def _has_split_payment(payment: PaymentReconciliation, payment_row_count: int | None = None) -> bool:
    if payment_row_count is not None:
        return payment_row_count >= 2
    return len(payment.payment_types) >= 2


def _primary_issue(
    facts: OrderFacts,
    payment: PaymentReconciliation,
    delivery: DeliveryAnalysis,
    payment_row_count: int | None = None,
) -> PrimaryIssue:
    if facts.order_status == "canceled" and _is_paid(payment):
        return "canceled_order_paid"
    if facts.order_status == "unavailable" and _is_paid(payment):
        return "unavailable_order_paid"
    if _is_late_delivery(delivery) and delivery.late_handoff_seller_ids:
        return "late_delivery_seller"
    if _is_late_delivery(delivery):
        return "late_delivery_logistics"
    if _has_split_payment(payment, payment_row_count) and payment.reconciled is True:
        return "valid_split_payment"
    return "unsupported_late_claim"


def _secondary_issues(
    facts: OrderFacts,
    customer: CustomerContext,
    payment: PaymentReconciliation,
    payment_row_count: int | None = None,
) -> list[str]:
    issues: list[str] = []
    if len(facts.items) >= 2:
        issues.append("multi_item_order")
    if len(facts.seller_ids) >= 2:
        issues.append("multi_seller_order")
    if _has_split_payment(payment, payment_row_count):
        issues.append("split_payment")
    if customer.related_order_ids:
        issues.append("repeat_customer")
    if len(facts.category_names) >= 2:
        issues.append("multiple_categories")
    return issues


def _responsible_parties(primary: PrimaryIssue, delivery: DeliveryAnalysis) -> list[ResponsibleParty]:
    rule = POLICY_RULES[primary]
    if rule.party_type is None:
        return []
    if rule.fixed_party_id is not None:
        return [ResponsibleParty(party_type=rule.party_type, party_id=rule.fixed_party_id)]
    return [
        ResponsibleParty(party_type=rule.party_type, party_id=seller_id)
        for seller_id in delivery.late_handoff_seller_ids[:3]
    ]


def _refund(primary: PrimaryIssue, payment: PaymentReconciliation) -> float:
    basis = POLICY_RULES[primary].refund_basis
    if basis == "payment_total":
        return payment.payment_total_brl
    if basis == "freight_total":
        return payment.freight_total_brl or 0.0
    return 0.0


def _actions(
    primary: PrimaryIssue,
    facts: OrderFacts,
    payment: PaymentReconciliation,
    payment_row_count: int | None = None,
) -> list[str]:
    actions = [POLICY_RULES[primary].primary_action]
    if primary == "late_delivery_seller":
        actions.append("review_seller_handoff")
    elif primary == "late_delivery_logistics":
        actions.append("review_carrier_delay")

    # Only a FULL refund needs its completion verified. The README section 6 worked example
    # is this very order (eb09635680fadffb33358e40b05c9029) and its action list is
    # ["refund_freight", "review_seller_handoff", "verify_payment_allocation"] — no
    # verify_refund_completion, even though a freight refund is recommended.
    if POLICY_RULES[primary].primary_action == "issue_full_refund":
        actions.append("verify_refund_completion")
    if len(facts.seller_ids) >= 2:
        actions.append("coordinate_multi_seller_case")
    if _has_split_payment(payment, payment_row_count) and primary != "valid_split_payment":
        actions.append("verify_payment_allocation")
    return actions[:5]


def _confidence(facts: OrderFacts, payment: PaymentReconciliation, delivery: DeliveryAnalysis) -> float:
    confidence = 0.95
    if delivery.delivered_at is None or delivery.carrier_handoff_at is None:
        confidence -= 0.10
    if not facts.has_items:
        confidence -= 0.10
    if payment.difference_brl is not None and 0.05 < abs(payment.difference_brl) <= 0.10:
        confidence -= 0.05
    return max(0.30, min(0.98, round(confidence, 2)))


def decide(
    facts: OrderFacts,
    customer: CustomerContext,
    payment: PaymentReconciliation,
    delivery: DeliveryAnalysis,
    *,
    payment_row_count: int | None = None,
) -> Verdict:
    """Apply PRIMARY_ISSUE_PRECEDENCE, then build the rest of the verdict around it."""
    primary = _primary_issue(facts, payment, delivery, payment_row_count)
    rule = POLICY_RULES[primary]
    return Verdict(
        case_assessment=CaseAssessment(
            primary_issue=primary,
            secondary_issues=_secondary_issues(facts, customer, payment, payment_row_count),
            case_status=rule.case_status,
            confidence=_confidence(facts, payment, delivery),
        ),
        root_cause_analysis=RootCauseAnalysis(
            ranked_causes=[RankedCause(cause_code=rule.rank1_cause, rank=1)],
            responsible_parties=_responsible_parties(primary, delivery),
        ),
        financial_resolution=FinancialResolution(recommended_refund_brl=_refund(primary, payment)),
        resolution_actions=_actions(primary, facts, payment, payment_row_count),
    )
