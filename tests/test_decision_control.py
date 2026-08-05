from __future__ import annotations

from ec_dispute.contracts import (
    A2AEnvelope,
    AffectedEntities,
    CaseAssessment,
    CandidateOutput,
    CustomerContext,
    DeliveryAnalysis,
    FinancialResolution,
    OrderFacts,
    OrderItemFact,
    PaymentReconciliation,
    ProductContext,
    RankedCause,
    ResponsibleParty,
    RootCauseAnalysis,
    SellerHandoffAnalysis,
    build_envelope_id,
    utc_now_z,
)
from ec_dispute.policy_engine import decide
from ec_dispute.verifier import verify

ORDER = "9b75cdaf2d85857ef023980e15d01546"
SELLER = "4a3ca9315b744ce9f8e9374361493884"
PRODUCT = "1e9e8ef04dbcff4541ed26657ea517e5"
CUSTOMER = "871766c5855e863f6eccc05f988b23cb"
CUSTOMER_UNIQUE = "861eff4711a542e4b93843c6dd7febb0"


class FakeStore:
    def __init__(self, existing: set[str]) -> None:
        self.existing = existing

    def key_exists(self, reference: str) -> bool:
        return reference in self.existing


def _facts() -> OrderFacts:
    return OrderFacts(
        order_id=ORDER,
        customer_id=CUSTOMER,
        order_status="delivered",
        order_delivered_carrier_at="2018-03-15 21:33:51",
        order_delivered_customer_at="2018-03-31 15:23:33",
        order_estimated_delivery_at="2018-03-28 00:00:00",
        has_items=True,
        items=[
            OrderItemFact(
                order_id=ORDER,
                order_item_id=1,
                product_id=PRODUCT,
                seller_id=SELLER,
                shipping_limit_at="2018-03-15 20:31:15",
                price_brl=194.0,
                freight_value_brl=18.27,
                category_name="cama_mesa_banho",
            )
        ],
        seller_ids=[SELLER],
        product_ids=[PRODUCT],
        category_names=["cama_mesa_banho"],
    )


def _payment() -> PaymentReconciliation:
    return PaymentReconciliation(
        item_total_brl=194.0,
        freight_total_brl=18.27,
        expected_total_brl=212.27,
        payment_total_brl=212.27,
        difference_brl=0.0,
        reconciled=True,
        payment_types=["credit_card", "voucher"],
    )


def _delivery() -> DeliveryAnalysis:
    return DeliveryAnalysis(
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
    )


def _candidate() -> CandidateOutput:
    return CandidateOutput(
        case_id="EC_002",
        case_assessment=CaseAssessment(
            primary_issue="late_delivery_seller",
            secondary_issues=["split_payment"],
            case_status="action_required",
            confidence=0.95,
        ),
        affected_entities=AffectedEntities(
            order_ids=[ORDER],
            item_ids=[f"{ORDER}:1"],
            seller_ids=[SELLER],
            payment_ids=[f"{ORDER}:1", f"{ORDER}:2"],
        ),
        customer_context=CustomerContext(customer_unique_id=CUSTOMER_UNIQUE, related_order_ids=[]),
        product_context=ProductContext(product_ids=[PRODUCT], category_names=["cama_mesa_banho"]),
        delivery_analysis=_delivery(),
        payment_reconciliation=_payment(),
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
        resolution_actions=[
            "refund_freight",
            "review_seller_handoff",
            "verify_refund_completion",
            "verify_payment_allocation",
        ],
    )


def _upstream(provenance: list[str]) -> list[A2AEnvelope]:
    return [
        A2AEnvelope(
            envelope_id=build_envelope_id("EC_002", "T3", "A2_customer"),
            case_id="EC_002",
            from_agent="A2_customer",
            to_agent="A5_policy",
            stage="T3",
            produced_at=utc_now_z(),
            payload_type="customer_context",
            payload=CustomerContext(customer_unique_id=CUSTOMER_UNIQUE, related_order_ids=[]),
            provenance=provenance,
            tool_calls=["fake"],
            model="qwen3:4b-instruct",
        )
    ]


def test_policy_engine_selects_late_delivery_seller() -> None:
    verdict = decide(_facts(), CustomerContext(customer_unique_id=CUSTOMER_UNIQUE), _payment(), _delivery())

    assert verdict.case_assessment.primary_issue == "late_delivery_seller"
    assert verdict.financial_resolution.recommended_refund_brl == 18.27
    assert verdict.root_cause_analysis.responsible_parties[0].party_id == SELLER


def test_verifier_passes_with_provenance_and_existing_keys() -> None:
    candidate = _candidate()
    provenance = [e for e in candidate.evidence_ids if not e.startswith("policy:")]
    store = FakeStore(set(provenance) | {f"product:{PRODUCT}"})

    result = verify(candidate, _upstream(provenance), store)  # type: ignore[arg-type]

    assert result.status == "pass"


def test_verifier_fails_fabricated_evidence() -> None:
    candidate = _candidate()
    provenance = [f"order:{ORDER}", f"item:{ORDER}:1"]
    store = FakeStore(set(provenance) | {f"product:{PRODUCT}"})

    result = verify(candidate, _upstream(provenance), store)  # type: ignore[arg-type]

    assert result.status == "fail"
    assert "A6_evidence" in result.blamed_agents
