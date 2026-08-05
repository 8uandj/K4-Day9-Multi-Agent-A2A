"""Tests for the data plane: DataStore, lookups, and agents A1 / A2 / A6.

OWNER: Thanh vien 2 (Data & Entities)

Assertions use real values from the Olist CSVs rather than fixtures, because the failure
mode that costs points is a join that silently returns the wrong row — a mock would happily
reproduce the bug.
"""

from __future__ import annotations

import json

import pytest

from ec_dispute.agents.base import ToolPermissionError
from ec_dispute.agents.customer import CustomerAgent
from ec_dispute.agents.evidence import EvidenceAgent, payment_sequentials_from_provenance
from ec_dispute.agents.order_product import OrderProductAgent
from ec_dispute.contracts import (
    LIMITS,
    CaseAssessment,
    CaseInput,
    DeliveryAnalysis,
    FinancialResolution,
    PaymentReconciliation,
    RankedCause,
    RootCauseAnalysis,
    Verdict,
    validate_reference,
)
from ec_dispute.data_store import DataStore, get_store
from ec_dispute.paths import INPUT_DIR
from ec_dispute.tools.lookups import build_customer_context, build_order_facts, order_facts_provenance

# Ground truth read straight out of the CSVs.
EC_001_ORDER = "9b75cdaf2d85857ef023980e15d01546"
EC_001_CUSTOMER = "1790ea7644578180c232ae2249ee4486"
EC_001_UNIQUE = "bbf65e7823171a84e70a495dd6c34ceb"
EC_001_RELATED = "65bbd0719855fe808bb19f62dfa9f42c"
EC_009_ORDER = "6683aa4f73f7869ec65ebeeef53f700b"  # 5 items — on the cap
EC_012_ORDER = "73628c6d02ed8f6134d9752cd7b83c2a"  # unavailable, zero item rows
EC_049_ORDER = "7c29f6fa9efcbf410b4bbb9362b9f7c9"  # 3 sellers — on the cap


@pytest.fixture(scope="module")
def store() -> DataStore:
    return get_store()


def load_case(case_id: str) -> CaseInput:
    return CaseInput.model_validate(json.loads((INPUT_DIR / f"{case_id}.json").read_text(encoding="utf-8")))


# ---------------------------------------------------------------- DataStore


def test_store_skips_unused_datasets(store: DataStore) -> None:
    """reviews and geolocation are outside every agent's grant, so they are never parsed."""
    assert not hasattr(store, "_reviews")
    assert not hasattr(store, "_geolocation")


def test_items_come_back_in_order_item_id_order(store: DataStore) -> None:
    ids = [int(row["order_item_id"]) for row in store.items_for(EC_009_ORDER)]
    assert ids == [1, 2, 3, 4, 5]


def test_payments_come_back_in_sequential_order(store: DataStore) -> None:
    seqs = [int(row["payment_sequential"]) for row in store.payments_for(EC_049_ORDER)]
    assert seqs == sorted(seqs) and len(seqs) == 2


def test_blank_category_reads_as_none_not_empty_string(store: DataStore) -> None:
    """610/32951 products carry a blank category; an empty string would pollute category_names."""
    blank = next(pid for pid, row in store._products.items() if not row["product_category_name"].strip())
    assert store.category_of(blank) is None


def test_unknown_product_is_none_not_a_crash(store: DataStore) -> None:
    assert store.category_of("0" * 32) is None
    assert store.product("0" * 32) is None


def test_key_exists_accepts_real_rows(store: DataStore) -> None:
    assert store.key_exists(f"order:{EC_001_ORDER}")
    assert store.key_exists(f"item:{EC_009_ORDER}:5")
    assert store.key_exists(f"customer:{EC_001_CUSTOMER}")
    assert store.key_exists("policy:DELIVERY_WITHIN_ESTIMATE")


def test_key_exists_rejects_fabrications(store: DataStore) -> None:
    assert not store.key_exists(f"order:{'0' * 32}")
    assert not store.key_exists(f"item:{EC_009_ORDER}:99")  # order is real, that item row is not
    assert not store.key_exists("orders:" + EC_001_ORDER)  # wrong grammar
    assert not store.key_exists("policy:NOT_A_REAL_CODE")


# ---------------------------------------------------------------- order facts


def test_order_facts_for_ec_001(store: DataStore) -> None:
    facts = build_order_facts(store, EC_001_ORDER)
    assert facts.has_items is True
    assert [item.order_item_id for item in facts.items] == [1, 2]
    assert facts.seller_ids == ["c70c1b0d8ca86052f45a432a38b73958"]
    assert facts.category_names == ["beleza_saude"]
    assert facts.customer_id == EC_001_CUSTOMER
    assert facts.order_status == "delivered"


def test_order_with_no_items_reports_empty_everything(store: DataStore) -> None:
    """6/50 cases. has_items=False forces null reconciliation downstream, not 0.0."""
    facts = build_order_facts(store, EC_012_ORDER)
    assert facts.has_items is False
    assert facts.items == []
    assert facts.seller_ids == [] and facts.product_ids == [] and facts.category_names == []
    assert facts.seller_shipping_limits == []
    assert facts.order_status == "unavailable"


def test_sellers_keep_first_appearance_order(store: DataStore) -> None:
    facts = build_order_facts(store, EC_049_ORDER)
    assert facts.seller_ids == [
        "41b39e28db005d9731d9d485a83b4c38",
        "d2374cbcbb3ca4ab1086534108cc3ab7",
        "1900267e848ceeba8fa32d80c1a5f5a8",
    ]
    assert len(facts.seller_ids) == LIMITS["seller_ids"]  # exactly on the ceiling


def test_seller_shipping_limit_is_the_earliest_one(store: DataStore) -> None:
    """A4 measures handoff against the deadline that actually binds — the earliest."""
    facts = build_order_facts(store, EC_049_ORDER)
    for seller in facts.seller_shipping_limits:
        limits = [i.shipping_limit_at for i in facts.items if i.seller_id == seller.seller_id]
        assert seller.shipping_limit_at == min(limits)


def test_facts_are_not_truncated_to_output_limits(store: DataStore) -> None:
    """Capping here would corrupt A3's item totals; A6 caps instead."""
    facts = build_order_facts(store, EC_009_ORDER)
    assert len(facts.items) == 5
    assert len(store.items_for(EC_009_ORDER)) == len(facts.items)


def test_missing_order_fails_loudly(store: DataStore) -> None:
    with pytest.raises(KeyError, match="does not exist"):
        build_order_facts(store, "0" * 32)


def test_product_scope_off_drops_product_detail_but_keeps_sellers(store: DataStore) -> None:
    facts = build_order_facts(store, EC_001_ORDER, include_product_context=False)
    assert facts.product_ids == [] and facts.category_names == []
    assert facts.seller_ids  # the policy still needs to know who the seller is


def test_all_50_claimed_orders_build_facts(store: DataStore) -> None:
    for path in sorted(INPUT_DIR.glob("EC_*.json")):
        case = CaseInput.model_validate(json.loads(path.read_text(encoding="utf-8")))
        facts = build_order_facts(store, case.customer_request.claimed_order_id)
        assert facts.order_id == case.customer_request.claimed_order_id


# ---------------------------------------------------------------- customer context


def test_customer_context_for_repeat_customer(store: DataStore) -> None:
    context = build_customer_context(store, EC_001_CUSTOMER, EC_001_ORDER)
    assert context.customer_unique_id == EC_001_UNIQUE
    assert context.related_order_ids == [EC_001_RELATED]


def test_claimed_order_is_excluded_from_its_own_history(store: DataStore) -> None:
    context = build_customer_context(store, EC_001_CUSTOMER, EC_001_ORDER)
    assert EC_001_ORDER not in context.related_order_ids


def test_single_order_customer_has_no_related_orders(store: DataStore) -> None:
    facts = build_order_facts(store, EC_009_ORDER)
    context = build_customer_context(store, facts.customer_id, EC_009_ORDER)
    assert context.related_order_ids == []
    assert CustomerAgent.is_repeat_customer(context) is False


def test_history_scope_off_keeps_identity_drops_history(store: DataStore) -> None:
    context = build_customer_context(store, EC_001_CUSTOMER, EC_001_ORDER, include_history=False)
    assert context.customer_unique_id == EC_001_UNIQUE
    assert context.related_order_ids == []


def test_unknown_customer_returns_empty_context(store: DataStore) -> None:
    context = build_customer_context(store, "0" * 32, EC_001_ORDER)
    assert context.customer_unique_id is None and context.related_order_ids == []


# ---------------------------------------------------------------- provenance


def test_provenance_is_well_formed_and_resolvable(store: DataStore) -> None:
    facts = build_order_facts(store, EC_049_ORDER)
    refs = order_facts_provenance(facts)
    for ref in refs:
        validate_reference(ref, allow_provenance_kinds=True)
    assert store.missing_references(refs) == []


def test_provenance_covers_every_entity_a1_reports(store: DataStore) -> None:
    facts = build_order_facts(store, EC_001_ORDER)
    refs = set(order_facts_provenance(facts))
    for seller_id in facts.seller_ids:
        assert f"seller:{seller_id}" in refs
    for item in facts.items:
        assert f"item:{facts.order_id}:{item.order_item_id}" in refs


# ---------------------------------------------------------------- agents


def test_a1_emits_a_valid_t2_envelope(store: DataStore) -> None:
    envelope = OrderProductAgent(store=store).run(load_case("EC_001"))
    assert envelope.stage == "T2" and envelope.payload_type == "order_facts"
    assert envelope.from_agent == "A1_order_product"
    assert envelope.model == "qwen3:8b"
    assert envelope.envelope_id.startswith("EC_001#T2#")


def test_a2_emits_a_valid_t3_envelope(store: DataStore) -> None:
    case = load_case("EC_001")
    facts = OrderProductAgent(store=store).analyse(case)
    envelope = CustomerAgent(store=store).run(case, facts)
    assert envelope.stage == "T3" and envelope.payload_type == "customer_context"
    assert envelope.payload.customer_unique_id == EC_001_UNIQUE


def test_agent_cannot_call_a_tool_outside_its_grant(store: DataStore) -> None:
    agent = CustomerAgent(store=store)
    with pytest.raises(ToolPermissionError, match="may not call"):
        agent.check_tools(["read_order_payments"])


# ---------------------------------------------------------------- assembly (A6)


def _no_action_verdict() -> Verdict:
    return Verdict(
        case_assessment=CaseAssessment(
            primary_issue="unsupported_late_claim",
            secondary_issues=["multi_item_order", "repeat_customer"],
            case_status="no_action",
            confidence=0.95,
        ),
        root_cause_analysis=RootCauseAnalysis(
            ranked_causes=[RankedCause(cause_code="DELIVERY_WITHIN_ESTIMATE", rank=1)]
        ),
        financial_resolution=FinancialResolution(recommended_refund_brl=0.0),
        resolution_actions=["reject_late_refund"],
    )


def _reconciliation_for(facts) -> PaymentReconciliation:
    item_total = round(sum(i.price_brl for i in facts.items), 2)
    freight_total = round(sum(i.freight_value_brl for i in facts.items), 2)
    expected = round(item_total + freight_total, 2)
    return PaymentReconciliation(
        item_total_brl=item_total,
        freight_total_brl=freight_total,
        expected_total_brl=expected,
        payment_total_brl=expected,
        difference_brl=0.0,
        reconciled=True,
        payment_types=["credit_card"],
    )


def test_a6_assembles_a_valid_candidate_output(store: DataStore) -> None:
    case = load_case("EC_001")
    facts = OrderProductAgent(store=store).analyse(case)
    customer = CustomerAgent(store=store).analyse(case, facts)
    provenance = order_facts_provenance(facts) + [f"payment:{facts.order_id}:1"]

    envelope = EvidenceAgent().run(
        case.case_id, facts, customer, DeliveryAnalysis(), _reconciliation_for(facts),
        _no_action_verdict(), provenance,
    )
    candidate = envelope.payload

    assert envelope.stage == "T5" and envelope.to_agent == "A7_verifier"
    assert candidate.affected_entities.order_ids == [EC_001_ORDER]
    assert candidate.affected_entities.item_ids == [f"{EC_001_ORDER}:1", f"{EC_001_ORDER}:2"]
    assert candidate.affected_entities.payment_ids == [f"{EC_001_ORDER}:1"]
    assert candidate.customer_context.related_order_ids == [EC_001_RELATED]
    assert candidate.evidence_ids[0] == f"order:{EC_001_ORDER}"
    assert candidate.evidence_ids[-1] == "policy:DELIVERY_WITHIN_ESTIMATE"
    assert store.missing_references(candidate.evidence_ids) == []


def test_a6_payment_ids_come_from_a3_provenance() -> None:
    provenance = [f"payment:{EC_049_ORDER}:2", f"payment:{EC_049_ORDER}:1", f"order:{EC_049_ORDER}"]
    assert payment_sequentials_from_provenance(EC_049_ORDER, provenance) == [1, 2]


def test_a6_refuses_to_ship_empty_payment_ids_when_money_moved(store: DataStore) -> None:
    """A silent empty array costs points; a loud error naming A3 costs a minute."""
    case = load_case("EC_001")
    facts = OrderProductAgent(store=store).analyse(case)
    customer = CustomerAgent(store=store).analyse(case, facts)
    with pytest.raises(ValueError, match="declared no"):
        EvidenceAgent().assemble(
            case.case_id, facts, customer, DeliveryAnalysis(), _reconciliation_for(facts),
            _no_action_verdict(), order_facts_provenance(facts),  # no payment refs
        )


def test_a6_respects_the_evidence_budget() -> None:
    """Order and policy citations are mandatory, so they keep reserved slots under pressure."""

    class _Item:
        def __init__(self, n: int) -> None:
            self.order_item_id = n

    evidence = EvidenceAgent.build_evidence(
        EC_001_ORDER,
        [_Item(n) for n in range(1, 30)],
        list(range(1, 30)),
        [f"{i:032x}" for i in range(3)],
        _no_action_verdict(),
    )
    assert len(evidence) == LIMITS["evidence_ids"]
    assert evidence[0].startswith("order:")
    assert evidence[-1].startswith("policy:")
