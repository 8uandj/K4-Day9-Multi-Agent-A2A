"""FROZEN CONTRACT — graded output schema for EC_POLICY_V2.

This module defines everything the grader actually reads: the shape of
``output/EC_*.json``, the array limits, and the EC_POLICY_V2 decision table.

FREEZE RULES
------------
1. Nobody edits this file alone. A change here breaks every agent at once, so it
   needs agreement from all three owners plus a line in ``docs/team_workboard.md``.
2. Validators here encode rules stated verbatim in ``README.md`` section 4-6. If a
   validator rejects your output, the output is wrong — do not relax the validator.
3. Judgement calls that README leaves ambiguous are marked ``DECISION:`` with the
   reasoning and a single switch, so flipping one is a one-line change.

Invariants verified against the real CSVs before freezing:
- every order/customer/product/seller id is exactly 32 lowercase hex chars (0 exceptions
  across all 9 datasets)
- ``order_item_id`` ranges 1..21, ``payment_sequential`` ranges 1..29
- across the 50 claimed orders: max 5 items, 4 payments, 3 sellers, 2 related orders
  -> item (5/5) and seller (3/3) sit exactly on the schema ceiling, zero headroom
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

CONTRACT_VERSION = "1.0.0-frozen"

# --------------------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------------------


def _round2(value: object) -> object:
    """Round every money/hour figure to 2 decimals at the contract boundary.

    README section 4: "Mọi phép tính tiền và số giờ được làm tròn 2 chữ số thập phân."
    Doing it here means no agent can leak 87.38999999999999 into a graded field.
    Uses Python's ``round`` (banker's rounding on exact .5) because the reference
    implementation is almost certainly Python too.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    return value


Money2 = Annotated[float, BeforeValidator(_round2), Field(ge=0)]
SignedMoney2 = Annotated[float, BeforeValidator(_round2)]
# Hours are signed: delivering 3 days EARLY is a legitimate negative variance.
Hours2 = Annotated[float, BeforeValidator(_round2)]

OlistId = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
CaseId = Annotated[str, Field(pattern=r"^EC_\d{3}$")]
TimestampStr = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")]
Currency = Literal["BRL"]

OrderStatus = Literal[
    "approved", "canceled", "created", "delivered", "invoiced", "processing", "shipped", "unavailable"
]
PaymentType = Literal["boleto", "credit_card", "debit_card", "not_defined", "voucher"]


class StrictModel(BaseModel):
    """Reject unknown keys everywhere. A typo becomes an error, not a silently dropped field."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


def _reject_duplicates(values: list[str], label: str) -> list[str]:
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must not contain duplicates: {values}")
    return values


# --------------------------------------------------------------------------------------
# Array limits (README section 6)
# --------------------------------------------------------------------------------------

LIMITS: dict[str, int] = {
    "order_ids": 5,
    "item_ids": 5,
    "seller_ids": 3,
    "payment_ids": 5,
    "related_order_ids": 5,
    "product_ids": 5,
    "category_names": 5,
    "ranked_causes": 3,
    "responsible_parties": 3,
    "evidence_ids": 20,
    "resolution_actions": 5,
}

# --------------------------------------------------------------------------------------
# Taxonomy
# --------------------------------------------------------------------------------------

PrimaryIssue = Literal[
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
]
SecondaryIssue = Literal[
    "multi_item_order",
    "multi_seller_order",
    "split_payment",
    "repeat_customer",
    "multiple_categories",
]
CaseStatus = Literal["action_required", "no_action"]
PartyType = Literal["platform", "seller", "logistics_provider"]
CauseCode = Literal[
    "SELLER_HANDOFF_AFTER_LIMIT",
    "CARRIER_DELIVERED_AFTER_ESTIMATE",
    "ORDER_CANCELED_AFTER_PAYMENT",
    "ORDER_UNAVAILABLE_AFTER_PAYMENT",
    "MULTIPLE_PAYMENTS_RECONCILED",
    "DELIVERY_WITHIN_ESTIMATE",
]
ResolutionAction = Literal[
    "issue_full_refund",
    "refund_freight",
    "explain_valid_split_payment",
    "reject_late_refund",
    "review_seller_handoff",
    "review_carrier_delay",
    "verify_refund_completion",
    "coordinate_multi_seller_case",
    "verify_payment_allocation",
]

# Secondary issues are appended in this exact order (README section 4, list 1-5).
SECONDARY_ISSUE_ORDER: tuple[SecondaryIssue, ...] = (
    "multi_item_order",
    "multi_seller_order",
    "split_payment",
    "repeat_customer",
    "multiple_categories",
)

PRIMARY_ACTIONS: frozenset[str] = frozenset(
    {"issue_full_refund", "refund_freight", "explain_valid_split_payment", "reject_late_refund"}
)

# Follow-up actions come after the primary action, in this order. ``review_seller_handoff``
# and ``review_carrier_delay`` share rank 0 because README words them as alternatives
# ("review_seller_handoff hoặc review_carrier_delay") - at most one may appear.
FOLLOW_UP_ACTION_RANK: dict[str, int] = {
    "review_seller_handoff": 0,
    "review_carrier_delay": 0,
    "verify_refund_completion": 1,
    "coordinate_multi_seller_case": 2,
    "verify_payment_allocation": 3,
}

# --------------------------------------------------------------------------------------
# EC_POLICY_V2 decision table — single source of truth for A5 Policy Agent
# --------------------------------------------------------------------------------------

RefundBasis = Literal["payment_total", "freight_total", "none"]


class PolicyRule(StrictModel):
    """One row of the README section 4 table, in machine-readable form."""

    primary_issue: PrimaryIssue
    primary_action: ResolutionAction
    rank1_cause: CauseCode
    party_type: PartyType | None
    fixed_party_id: str | None
    refund_basis: RefundBasis
    case_status: CaseStatus


POLICY_RULES: dict[str, PolicyRule] = {
    rule.primary_issue: rule
    for rule in (
        PolicyRule(
            primary_issue="canceled_order_paid",
            primary_action="issue_full_refund",
            rank1_cause="ORDER_CANCELED_AFTER_PAYMENT",
            party_type="platform",
            fixed_party_id="OLIST_PLATFORM",
            refund_basis="payment_total",
            case_status="action_required",
        ),
        PolicyRule(
            primary_issue="unavailable_order_paid",
            primary_action="issue_full_refund",
            rank1_cause="ORDER_UNAVAILABLE_AFTER_PAYMENT",
            party_type="platform",
            fixed_party_id="OLIST_PLATFORM",
            refund_basis="payment_total",
            case_status="action_required",
        ),
        PolicyRule(
            primary_issue="late_delivery_seller",
            primary_action="refund_freight",
            rank1_cause="SELLER_HANDOFF_AFTER_LIMIT",
            party_type="seller",
            fixed_party_id=None,  # the offending seller ids, resolved per case
            refund_basis="freight_total",
            case_status="action_required",
        ),
        PolicyRule(
            primary_issue="late_delivery_logistics",
            primary_action="refund_freight",
            rank1_cause="CARRIER_DELIVERED_AFTER_ESTIMATE",
            party_type="logistics_provider",
            fixed_party_id="LOGISTICS_PROVIDER",
            refund_basis="freight_total",
            case_status="action_required",
        ),
        PolicyRule(
            primary_issue="valid_split_payment",
            primary_action="explain_valid_split_payment",
            rank1_cause="MULTIPLE_PAYMENTS_RECONCILED",
            party_type=None,
            fixed_party_id=None,
            refund_basis="none",
            case_status="no_action",
        ),
        PolicyRule(
            primary_issue="unsupported_late_claim",
            primary_action="reject_late_refund",
            rank1_cause="DELIVERY_WITHIN_ESTIMATE",
            party_type=None,
            fixed_party_id=None,
            refund_basis="none",
            case_status="no_action",
        ),
    )
}

# Evaluation order for A5. README section 4: "Áp dụng EC_POLICY_V2 theo thứ tự ưu tiên."
PRIMARY_ISSUE_PRECEDENCE: tuple[PrimaryIssue, ...] = (
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
)

RECONCILIATION_TOLERANCE_BRL = 0.10
"""``reconciled = abs(difference_brl) <= 0.10``. The boundary value 0.10 counts as reconciled."""

# DECISION (ambiguous in README): ``payment_types`` lists DISTINCT types in payment_sequential
# order, not one entry per payment row. Rationale: the field is named "types", and the README
# example pairs 2 payment rows with 2 types without disambiguating. Affects only 4/50 cases
# (EC_010, EC_015, EC_016, EC_042) where an order repeats a type, i.e. ~1.2% of total score.
# Flip this single flag if the leaderboard says otherwise.
PAYMENT_TYPES_DEDUPED = True

# --------------------------------------------------------------------------------------
# Evidence ID grammar (README section 5)
# --------------------------------------------------------------------------------------

EVIDENCE_KIND_ARITY: dict[str, int] = {"order": 2, "item": 3, "payment": 3, "seller": 2, "policy": 2}

# Provenance may additionally cite rows that are readable but never citable as evidence.
PROVENANCE_EXTRA_ARITY: dict[str, int] = {"customer": 2, "product": 2}

_CAUSE_CODES: frozenset[str] = frozenset(CauseCode.__args__)  # type: ignore[attr-defined]


def _is_hex32(value: str) -> bool:
    return len(value) == 32 and all(c in "0123456789abcdef" for c in value)


def validate_reference(ref: str, *, allow_provenance_kinds: bool = False) -> str:
    """Validate one evidence/provenance reference. Raises ``ValueError`` when malformed.

    README section 5: an evidence id that does not exist in the CSVs, or has the wrong
    shape, is counted as a false positive. This is the last place to catch that cheaply.
    """
    parts = ref.split(":")
    kind = parts[0]
    arity = dict(EVIDENCE_KIND_ARITY)
    if allow_provenance_kinds:
        arity.update(PROVENANCE_EXTRA_ARITY)
    if kind not in arity:
        raise ValueError(f"unknown reference kind {kind!r} in {ref!r}; allowed: {sorted(arity)}")
    if len(parts) != arity[kind]:
        raise ValueError(f"{kind} reference needs {arity[kind]} colon-separated parts: {ref!r}")

    if kind == "policy":
        if parts[1] not in _CAUSE_CODES:
            raise ValueError(f"policy reference must cite a known cause code: {ref!r}")
        return ref

    if not _is_hex32(parts[1]):
        raise ValueError(f"{kind} reference must carry a 32-char hex id: {ref!r}")

    if kind in ("item", "payment"):
        if not parts[2].isdigit() or int(parts[2]) < 1:
            raise ValueError(f"{kind} reference needs a positive integer suffix: {ref!r}")
    return ref


def order_evidence_id(order_id: str) -> str:
    return validate_reference(f"order:{order_id}")


def item_evidence_id(order_id: str, order_item_id: int) -> str:
    return validate_reference(f"item:{order_id}:{order_item_id}")


def payment_evidence_id(order_id: str, payment_sequential: int) -> str:
    return validate_reference(f"payment:{order_id}:{payment_sequential}")


def seller_evidence_id(seller_id: str) -> str:
    return validate_reference(f"seller:{seller_id}")


def policy_evidence_id(cause_code: str) -> str:
    return validate_reference(f"policy:{cause_code}")


def item_entity_id(order_id: str, order_item_id: int) -> str:
    """``affected_entities.item_ids`` element: ``<order_id>:<order_item_id>``."""
    return f"{order_id}:{order_item_id}"


def payment_entity_id(order_id: str, payment_sequential: int) -> str:
    """``affected_entities.payment_ids`` element: ``<order_id>:<payment_sequential>``."""
    return f"{order_id}:{payment_sequential}"


def _validate_entity_pair(value: str, label: str) -> str:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(f"{label} must be '<order_id>:<n>': {value!r}")
    if not _is_hex32(parts[0]):
        raise ValueError(f"{label} must start with a 32-char hex order id: {value!r}")
    if not parts[1].isdigit() or int(parts[1]) < 1:
        raise ValueError(f"{label} must end with a positive integer: {value!r}")
    return value


# --------------------------------------------------------------------------------------
# Graded output sections
# --------------------------------------------------------------------------------------


class CaseAssessment(StrictModel):
    primary_issue: PrimaryIssue
    secondary_issues: list[SecondaryIssue] = Field(default_factory=list, max_length=5)
    case_status: CaseStatus
    confidence: float = Field(ge=0, le=1)

    @field_validator("secondary_issues")
    @classmethod
    def canonical_order(cls, values: list[str]) -> list[str]:
        _reject_duplicates(values, "secondary_issues")
        ranks = [SECONDARY_ISSUE_ORDER.index(v) for v in values]  # type: ignore[arg-type]
        if ranks != sorted(ranks):
            raise ValueError(f"secondary_issues must follow {list(SECONDARY_ISSUE_ORDER)}, got {values}")
        return values


class AffectedEntities(StrictModel):
    order_ids: list[OlistId] = Field(default_factory=list, max_length=5)
    item_ids: list[str] = Field(default_factory=list, max_length=5)
    seller_ids: list[OlistId] = Field(default_factory=list, max_length=3)
    payment_ids: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("order_ids", "seller_ids")
    @classmethod
    def no_duplicate_ids(cls, values: list[str]) -> list[str]:
        return _reject_duplicates(values, "affected entity ids")

    @field_validator("item_ids")
    @classmethod
    def check_item_ids(cls, values: list[str]) -> list[str]:
        _reject_duplicates(values, "item_ids")
        return [_validate_entity_pair(v, "item_id") for v in values]

    @field_validator("payment_ids")
    @classmethod
    def check_payment_ids(cls, values: list[str]) -> list[str]:
        _reject_duplicates(values, "payment_ids")
        return [_validate_entity_pair(v, "payment_id") for v in values]


class CustomerContext(StrictModel):
    customer_unique_id: OlistId | None = None
    related_order_ids: list[OlistId] = Field(default_factory=list, max_length=5)

    @field_validator("related_order_ids")
    @classmethod
    def no_duplicates(cls, values: list[str]) -> list[str]:
        return _reject_duplicates(values, "related_order_ids")


class ProductContext(StrictModel):
    product_ids: list[OlistId] = Field(default_factory=list, max_length=5)
    category_names: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("product_ids", "category_names")
    @classmethod
    def no_duplicates(cls, values: list[str]) -> list[str]:
        return _reject_duplicates(values, "product context values")


class SellerHandoffAnalysis(StrictModel):
    seller_id: OlistId
    shipping_limit_at: TimestampStr | None = None
    handoff_variance_hours: Hours2 | None = None
    late_handoff: bool

    @model_validator(mode="after")
    def missing_evidence_is_not_a_violation(self) -> "SellerHandoffAnalysis":
        # Architecture principle: absence of evidence is not evidence of a breach.
        if self.handoff_variance_hours is None and self.late_handoff:
            raise ValueError("late_handoff cannot be true while handoff_variance_hours is null")
        return self


class DeliveryAnalysis(StrictModel):
    delivered_at: TimestampStr | None = None
    estimated_delivery_at: TimestampStr | None = None
    carrier_handoff_at: TimestampStr | None = None
    delivery_variance_hours: Hours2 | None = None
    seller_handoff_analysis: list[SellerHandoffAnalysis] = Field(default_factory=list, max_length=3)
    late_handoff_seller_ids: list[OlistId] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def variance_requires_both_timestamps(self) -> "DeliveryAnalysis":
        has_pair = self.delivered_at is not None and self.estimated_delivery_at is not None
        if self.delivery_variance_hours is not None and not has_pair:
            raise ValueError("delivery_variance_hours requires both delivered_at and estimated_delivery_at")
        if has_pair and self.delivery_variance_hours is None:
            raise ValueError("delivery_variance_hours must be computed when both timestamps exist")

        flagged = {row.seller_id for row in self.seller_handoff_analysis if row.late_handoff}
        if set(self.late_handoff_seller_ids) != flagged:
            raise ValueError("late_handoff_seller_ids must exactly match sellers flagged in seller_handoff_analysis")
        return self


class PaymentReconciliation(StrictModel):
    currency: Currency = "BRL"
    item_total_brl: Money2 | None = None
    freight_total_brl: Money2 | None = None
    expected_total_brl: Money2 | None = None
    payment_total_brl: Money2
    difference_brl: SignedMoney2 | None = None
    reconciled: bool | None = None
    payment_types: list[PaymentType] = Field(default_factory=list)

    @model_validator(mode="after")
    def all_null_or_all_present(self) -> "PaymentReconciliation":
        """README section 4: an order with no item row reports null for expected/difference/reconciled.

        DECISION: item_total_brl and freight_total_brl go null too. README only names three
        fields, but reporting 0.0 for item_total while expected_total is null would be
        internally contradictory (expected = item + freight).
        """
        nullable = [
            self.item_total_brl,
            self.freight_total_brl,
            self.expected_total_brl,
            self.difference_brl,
            self.reconciled,
        ]
        if any(v is None for v in nullable) and any(v is not None for v in nullable):
            raise ValueError("item/freight/expected/difference/reconciled must be all null or all present")

        if self.expected_total_brl is not None:
            expected = round(self.item_total_brl + self.freight_total_brl, 2)  # type: ignore[operator]
            if abs(expected - self.expected_total_brl) > 0.005:
                raise ValueError(f"expected_total_brl must equal item+freight ({expected}), got {self.expected_total_brl}")
            difference = round(self.payment_total_brl - self.expected_total_brl, 2)
            if abs(difference - self.difference_brl) > 0.005:  # type: ignore[operator]
                raise ValueError(f"difference_brl must equal payment-expected ({difference}), got {self.difference_brl}")
            if self.reconciled is not (abs(self.difference_brl) <= RECONCILIATION_TOLERANCE_BRL):  # type: ignore[arg-type]
                raise ValueError("reconciled must equal abs(difference_brl) <= 0.10")
        return self

    @field_validator("payment_types")
    @classmethod
    def deduped_when_configured(cls, values: list[str]) -> list[str]:
        if PAYMENT_TYPES_DEDUPED:
            _reject_duplicates(values, "payment_types (PAYMENT_TYPES_DEDUPED=True)")
        return values


class ResponsibleParty(StrictModel):
    party_type: PartyType
    party_id: str = Field(min_length=1)


class RankedCause(StrictModel):
    cause_code: CauseCode
    rank: int = Field(ge=1, le=3)


class RootCauseAnalysis(StrictModel):
    ranked_causes: list[RankedCause] = Field(default_factory=list, max_length=3)
    responsible_parties: list[ResponsibleParty] = Field(default_factory=list, max_length=3)

    @field_validator("ranked_causes")
    @classmethod
    def ranks_are_dense_and_ascending(cls, values: list[RankedCause]) -> list[RankedCause]:
        ranks = [c.rank for c in values]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError(f"ranked_causes ranks must be 1..n ascending, got {ranks}")
        _reject_duplicates([c.cause_code for c in values], "ranked_causes cause codes")
        return values


class FinancialResolution(StrictModel):
    currency: Currency = "BRL"
    recommended_refund_brl: Money2


# --------------------------------------------------------------------------------------
# Cross-section consistency (shared by Verdict and CandidateOutput)
# --------------------------------------------------------------------------------------


def check_resolution_consistency(
    assessment: CaseAssessment,
    root_cause: RootCauseAnalysis,
    financial: FinancialResolution,
    actions: list[str],
) -> None:
    """Enforce the README section 4 table. Raises ``ValueError`` on the first violation."""
    rule = POLICY_RULES[assessment.primary_issue]

    if not actions:
        raise ValueError("resolution_actions must contain at least the primary action")
    if actions[0] != rule.primary_action:
        raise ValueError(f"{assessment.primary_issue} requires first action {rule.primary_action!r}, got {actions[0]!r}")

    follow_ups = actions[1:]
    _reject_duplicates(list(actions), "resolution_actions")
    for action in follow_ups:
        if action in PRIMARY_ACTIONS:
            raise ValueError(f"{action!r} is a primary action and cannot appear as a follow-up")
    ranks = [FOLLOW_UP_ACTION_RANK[a] for a in follow_ups]
    if ranks != sorted(ranks):
        raise ValueError(f"follow-up actions out of order: {follow_ups}")
    if "review_seller_handoff" in follow_ups and "review_carrier_delay" in follow_ups:
        raise ValueError("review_seller_handoff and review_carrier_delay are alternatives; pick one")
    # README section 4: the primary action already explains the split, so do not add this one.
    if assessment.primary_issue == "valid_split_payment" and "verify_payment_allocation" in follow_ups:
        raise ValueError("verify_payment_allocation is forbidden when primary_issue is valid_split_payment")

    if root_cause.ranked_causes and root_cause.ranked_causes[0].cause_code != rule.rank1_cause:
        raise ValueError(
            f"{assessment.primary_issue} requires rank-1 cause {rule.rank1_cause!r}, "
            f"got {root_cause.ranked_causes[0].cause_code!r}"
        )

    if rule.party_type is None:
        if root_cause.responsible_parties:
            raise ValueError(f"{assessment.primary_issue} has no responsible party, got {root_cause.responsible_parties}")
    else:
        if not root_cause.responsible_parties:
            raise ValueError(f"{assessment.primary_issue} requires a responsible party of type {rule.party_type!r}")
        for party in root_cause.responsible_parties:
            if party.party_type != rule.party_type:
                raise ValueError(f"responsible party type must be {rule.party_type!r}, got {party.party_type!r}")
            if rule.fixed_party_id is not None and party.party_id != rule.fixed_party_id:
                raise ValueError(f"party_id must be {rule.fixed_party_id!r}, got {party.party_id!r}")
            if rule.fixed_party_id is None and not _is_hex32(party.party_id):
                raise ValueError(f"seller party_id must be a 32-char hex seller id, got {party.party_id!r}")

    refund = financial.recommended_refund_brl
    if rule.refund_basis == "none" and refund != 0:
        raise ValueError(f"{assessment.primary_issue} carries no refund, got {refund}")
    expected_status: CaseStatus = "action_required" if refund > 0 else "no_action"
    if assessment.case_status != expected_status:
        raise ValueError(f"case_status must be {expected_status!r} when recommended_refund_brl is {refund}")


class Verdict(StrictModel):
    """A5 Policy Agent output — the adjudication, before entities and evidence are attached."""

    case_assessment: CaseAssessment
    root_cause_analysis: RootCauseAnalysis
    financial_resolution: FinancialResolution
    resolution_actions: list[ResolutionAction] = Field(default_factory=list, min_length=1, max_length=5)

    @model_validator(mode="after")
    def consistent_with_policy_table(self) -> "Verdict":
        check_resolution_consistency(
            self.case_assessment, self.root_cause_analysis, self.financial_resolution, list(self.resolution_actions)
        )
        return self


class CandidateOutput(StrictModel):
    """The graded artifact. Field order matches README section 6 exactly — do not reorder."""

    case_id: CaseId
    case_assessment: CaseAssessment
    affected_entities: AffectedEntities
    customer_context: CustomerContext
    product_context: ProductContext
    delivery_analysis: DeliveryAnalysis
    payment_reconciliation: PaymentReconciliation
    root_cause_analysis: RootCauseAnalysis
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    financial_resolution: FinancialResolution
    resolution_actions: list[ResolutionAction] = Field(default_factory=list, min_length=1, max_length=5)

    @field_validator("evidence_ids")
    @classmethod
    def well_formed_evidence(cls, values: list[str]) -> list[str]:
        _reject_duplicates(values, "evidence_ids")
        for value in values:
            validate_reference(value)
        kinds = {v.split(":")[0] for v in values}
        if "order" not in kinds:
            raise ValueError("evidence_ids must cite the order")
        if "policy" not in kinds:
            raise ValueError("evidence_ids must cite the policy root cause")
        return values

    @model_validator(mode="after")
    def internally_consistent(self) -> "CandidateOutput":
        check_resolution_consistency(
            self.case_assessment, self.root_cause_analysis, self.financial_resolution, list(self.resolution_actions)
        )

        seller_ids = set(self.affected_entities.seller_ids)
        late = set(self.delivery_analysis.late_handoff_seller_ids)
        if not late <= seller_ids:
            raise ValueError(f"late_handoff_seller_ids {late - seller_ids} missing from affected_entities.seller_ids")

        for party in self.root_cause_analysis.responsible_parties:
            if party.party_type == "seller" and party.party_id not in seller_ids:
                raise ValueError(f"responsible seller {party.party_id} missing from affected_entities.seller_ids")

        cited_orders = {v.split(":")[1] for v in self.evidence_ids if v.startswith("order:")}
        if cited_orders != set(self.affected_entities.order_ids):
            raise ValueError("order evidence must match affected_entities.order_ids exactly")

        # README section 3: history orders live in customer_context only, never in affected_entities.
        overlap = set(self.customer_context.related_order_ids) & set(self.affected_entities.order_ids)
        if overlap:
            raise ValueError(f"related_order_ids must not appear in affected_entities.order_ids: {overlap}")
        return self

    def to_output_json(self) -> dict:
        """Serialise in README key order, with null preserved (never dropped)."""
        return self.model_dump(mode="json", exclude_none=False)
