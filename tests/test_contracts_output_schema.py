"""Contract tests for the graded output schema.

Positive tests pin the shape down; the negative tests are the point. Each one encodes a
mistake that would silently cost points if the contract let it through.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ec_dispute.contracts import (
    LIMITS,
    POLICY_RULES,
    SECONDARY_ISSUE_ORDER,
    AffectedEntities,
    CandidateOutput,
    CaseAssessment,
    CustomerContext,
    DeliveryAnalysis,
    FinancialResolution,
    PaymentReconciliation,
    ProductContext,
    RankedCause,
    ResponsibleParty,
    RootCauseAnalysis,
    SellerHandoffAnalysis,
    Verdict,
    item_evidence_id,
    validate_reference,
)

ORDER = "9b75cdaf2d85857ef023980e15d01546"
SELLER = "4a3ca9315b744ce9f8e9374361493884"
PRODUCT = "1e9e8ef04dbcff4541ed26657ea517e5"
CUSTOMER_UNIQUE = "861eff4711a542e4b93843c6dd7febb0"


def _late_seller_output(**overrides) -> CandidateOutput:
    base = dict(
        case_id="EC_002",
        case_assessment=CaseAssessment(
            primary_issue="late_delivery_seller",
            secondary_issues=["multi_item_order", "split_payment"],
            case_status="action_required",
            confidence=0.92,
        ),
        affected_entities=AffectedEntities(
            order_ids=[ORDER],
            item_ids=[f"{ORDER}:1"],
            seller_ids=[SELLER],
            payment_ids=[f"{ORDER}:1", f"{ORDER}:2"],
        ),
        customer_context=CustomerContext(customer_unique_id=CUSTOMER_UNIQUE, related_order_ids=[]),
        product_context=ProductContext(product_ids=[PRODUCT], category_names=["cama_mesa_banho"]),
        delivery_analysis=DeliveryAnalysis(
            delivered_at="2018-03-31 15:23:33",
            estimated_delivery_at="2018-03-28 00:00:00",
            carrier_handoff_at="2018-03-15 21:33:51",
            delivery_variance_hours=87.39,
            seller_handoff_analysis=[
                SellerHandoffAnalysis(
                    seller_id=SELLER,
                    shipping_limit_at="2018-03-15 20:31:15",
                    handoff_variance_hours=1.04,
                    late_handoff=True,
                )
            ],
            late_handoff_seller_ids=[SELLER],
        ),
        payment_reconciliation=PaymentReconciliation(
            item_total_brl=194.0,
            freight_total_brl=18.27,
            expected_total_brl=212.27,
            payment_total_brl=212.27,
            difference_brl=0.0,
            reconciled=True,
            payment_types=["credit_card", "voucher"],
        ),
        root_cause_analysis=RootCauseAnalysis(
            ranked_causes=[RankedCause(cause_code="SELLER_HANDOFF_AFTER_LIMIT", rank=1)],
            responsible_parties=[ResponsibleParty(party_type="seller", party_id=SELLER)],
        ),
        evidence_ids=[
            f"order:{ORDER}",
            f"item:{ORDER}:1",
            f"payment:{ORDER}:1",
            f"payment:{ORDER}:2",
            f"seller:{SELLER}",
            "policy:SELLER_HANDOFF_AFTER_LIMIT",
        ],
        financial_resolution=FinancialResolution(recommended_refund_brl=18.27),
        resolution_actions=["refund_freight", "review_seller_handoff", "verify_payment_allocation"],
    )
    base.update(overrides)
    return CandidateOutput(**base)


# ---------------------------------------------------------------- positive


def test_readme_example_validates() -> None:
    """The worked example from README section 6 must pass unchanged."""
    output = _late_seller_output()
    assert output.to_output_json()["case_assessment"]["primary_issue"] == "late_delivery_seller"


def test_output_key_order_matches_readme() -> None:
    assert list(_late_seller_output().to_output_json()) == [
        "case_id",
        "case_assessment",
        "affected_entities",
        "customer_context",
        "product_context",
        "delivery_analysis",
        "payment_reconciliation",
        "root_cause_analysis",
        "evidence_ids",
        "financial_resolution",
        "resolution_actions",
    ]


def test_money_and_hours_round_to_two_decimals() -> None:
    recon = PaymentReconciliation(
        item_total_brl=194.0,
        freight_total_brl=18.266666,
        expected_total_brl=212.266666,
        payment_total_brl=212.27,
        difference_brl=0.0033333,
        reconciled=True,
        payment_types=["credit_card"],
    )
    assert recon.freight_total_brl == 18.27
    assert recon.difference_brl == 0.0


def test_no_item_order_reports_all_nulls() -> None:
    """6/50 cases have no item row: expected/difference/reconciled must be null, not 0."""
    recon = PaymentReconciliation(payment_total_brl=59.9)
    assert recon.expected_total_brl is None and recon.reconciled is None


def test_reconciliation_boundary_is_inclusive() -> None:
    recon = PaymentReconciliation(
        item_total_brl=100.0,
        freight_total_brl=0.0,
        expected_total_brl=100.0,
        payment_total_brl=100.10,
        difference_brl=0.10,
        reconciled=True,
        payment_types=["boleto"],
    )
    assert recon.reconciled is True


def test_delivery_variance_may_be_negative() -> None:
    """Delivered early is a legitimate negative variance, not an error."""
    analysis = DeliveryAnalysis(
        delivered_at="2018-03-20 10:00:00",
        estimated_delivery_at="2018-03-28 00:00:00",
        delivery_variance_hours=-182.0,
    )
    assert analysis.delivery_variance_hours == -182.0


def test_every_policy_rule_is_reachable() -> None:
    assert set(POLICY_RULES) == {
        "canceled_order_paid",
        "unavailable_order_paid",
        "late_delivery_seller",
        "late_delivery_logistics",
        "valid_split_payment",
        "unsupported_late_claim",
    }


# ---------------------------------------------------------------- negative


def test_rejects_secondary_issues_out_of_order() -> None:
    with pytest.raises(ValidationError, match="secondary_issues must follow"):
        CaseAssessment(
            primary_issue="late_delivery_seller",
            secondary_issues=["split_payment", "multi_item_order"],
            case_status="action_required",
            confidence=0.9,
        )


def test_rejects_wrong_primary_action_for_issue() -> None:
    with pytest.raises(ValidationError, match="requires first action"):
        _late_seller_output(resolution_actions=["issue_full_refund"])


def test_rejects_verify_payment_allocation_on_valid_split_payment() -> None:
    with pytest.raises(ValidationError, match="forbidden when primary_issue is valid_split_payment"):
        Verdict(
            case_assessment=CaseAssessment(
                primary_issue="valid_split_payment", case_status="no_action", confidence=0.9
            ),
            root_cause_analysis=RootCauseAnalysis(
                ranked_causes=[RankedCause(cause_code="MULTIPLE_PAYMENTS_RECONCILED", rank=1)]
            ),
            financial_resolution=FinancialResolution(recommended_refund_brl=0.0),
            resolution_actions=["explain_valid_split_payment", "verify_payment_allocation"],
        )


def test_rejects_follow_up_actions_out_of_order() -> None:
    with pytest.raises(ValidationError, match="follow-up actions out of order"):
        _late_seller_output(
            resolution_actions=["refund_freight", "verify_payment_allocation", "review_seller_handoff"]
        )


def test_rejects_refund_status_mismatch() -> None:
    with pytest.raises(ValidationError, match="case_status must be"):
        _late_seller_output(financial_resolution=FinancialResolution(recommended_refund_brl=0.0))


def test_rejects_responsible_party_on_no_fault_issue() -> None:
    with pytest.raises(ValidationError, match="has no responsible party"):
        Verdict(
            case_assessment=CaseAssessment(
                primary_issue="unsupported_late_claim", case_status="no_action", confidence=0.9
            ),
            root_cause_analysis=RootCauseAnalysis(
                ranked_causes=[RankedCause(cause_code="DELIVERY_WITHIN_ESTIMATE", rank=1)],
                responsible_parties=[ResponsibleParty(party_type="platform", party_id="OLIST_PLATFORM")],
            ),
            financial_resolution=FinancialResolution(recommended_refund_brl=0.0),
            resolution_actions=["reject_late_refund"],
        )


def test_rejects_cause_code_not_matching_primary_issue() -> None:
    with pytest.raises(ValidationError, match="requires rank-1 cause"):
        _late_seller_output(
            root_cause_analysis=RootCauseAnalysis(
                ranked_causes=[RankedCause(cause_code="DELIVERY_WITHIN_ESTIMATE", rank=1)],
                responsible_parties=[ResponsibleParty(party_type="seller", party_id=SELLER)],
            )
        )


def test_rejects_late_handoff_without_variance() -> None:
    """Absence of a carrier timestamp is not evidence the seller was late."""
    with pytest.raises(ValidationError, match="late_handoff cannot be true"):
        SellerHandoffAnalysis(seller_id=SELLER, handoff_variance_hours=None, late_handoff=True)


def test_rejects_variance_computed_without_both_timestamps() -> None:
    with pytest.raises(ValidationError, match="requires both delivered_at"):
        DeliveryAnalysis(delivered_at=None, estimated_delivery_at="2018-03-28 00:00:00", delivery_variance_hours=5.0)


def test_rejects_partial_null_reconciliation() -> None:
    with pytest.raises(ValidationError, match="all null or all present"):
        PaymentReconciliation(item_total_brl=10.0, payment_total_brl=10.0)


def test_rejects_arithmetic_that_does_not_add_up() -> None:
    with pytest.raises(ValidationError, match="must equal item\\+freight"):
        PaymentReconciliation(
            item_total_brl=100.0,
            freight_total_brl=10.0,
            expected_total_brl=999.0,
            payment_total_brl=110.0,
            difference_brl=-889.0,
            reconciled=False,
            payment_types=["boleto"],
        )


def test_rejects_hallucinated_id_shape() -> None:
    with pytest.raises(ValidationError):
        AffectedEntities(order_ids=["not-a-real-order-id"])


def test_rejects_malformed_evidence_ids() -> None:
    for bad in ["orders:" + ORDER, f"item:{ORDER}", f"item:{ORDER}:0", "policy:NOT_A_CAUSE", f"seller:{ORDER[:8]}"]:
        with pytest.raises(ValueError):
            validate_reference(bad)


def test_rejects_evidence_missing_order_or_policy() -> None:
    with pytest.raises(ValidationError, match="must cite the policy root cause"):
        _late_seller_output(evidence_ids=[f"order:{ORDER}", item_evidence_id(ORDER, 1)])


def test_rejects_history_order_leaking_into_affected_entities() -> None:
    """README section 3: history orders belong to customer_context only."""
    with pytest.raises(ValidationError, match="must not appear in affected_entities"):
        _late_seller_output(
            customer_context=CustomerContext(customer_unique_id=CUSTOMER_UNIQUE, related_order_ids=[ORDER])
        )


def test_rejects_responsible_seller_absent_from_entities() -> None:
    other = "0" * 32
    with pytest.raises(ValidationError, match="missing from affected_entities.seller_ids"):
        _late_seller_output(
            root_cause_analysis=RootCauseAnalysis(
                ranked_causes=[RankedCause(cause_code="SELLER_HANDOFF_AFTER_LIMIT", rank=1)],
                responsible_parties=[ResponsibleParty(party_type="seller", party_id=other)],
            )
        )


def test_rejects_array_over_limit() -> None:
    with pytest.raises(ValidationError):
        AffectedEntities(seller_ids=[f"{i:032x}" for i in range(LIMITS["seller_ids"] + 1)])


def test_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        FinancialResolution(recommended_refund_brl=1.0, currency="BRL", note="oops")


def test_secondary_issue_order_matches_readme() -> None:
    assert SECONDARY_ISSUE_ORDER == (
        "multi_item_order",
        "multi_seller_order",
        "split_payment",
        "repeat_customer",
        "multiple_categories",
    )
