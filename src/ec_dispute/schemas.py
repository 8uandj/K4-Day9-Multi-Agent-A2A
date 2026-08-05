"""Shared Pydantic contracts for the EC_POLICY_V2 multi-agent pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TimestampStr = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")]
IsoTimestampStr = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")]
OrderId = Annotated[str, Field(min_length=1)]
CustomerId = Annotated[str, Field(min_length=1)]
ProductId = Annotated[str, Field(min_length=1)]
SellerId = Annotated[str, Field(min_length=1)]
Currency = Literal["BRL"]
PolicyVersion = Literal["EC_POLICY_V2"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class CustomerRequest(StrictModel):
    language: str = Field(default="vi", min_length=2)
    message: str = Field(min_length=1)
    claimed_order_id: OrderId


class InvestigationScope(StrictModel):
    include_customer_history: bool = True
    include_product_context: bool = True


class CaseInput(StrictModel):
    case_id: Annotated[str, Field(pattern=r"^EC_\d{3}$")]
    customer_request: CustomerRequest
    investigation_scope: InvestigationScope
    policy_version: PolicyVersion


AgentName = Literal[
    "A0_coordinator",
    "A1_order_product",
    "A2_customer",
    "A3_payment",
    "A4_delivery",
    "A5_policy",
    "A6_evidence",
    "A7_verifier",
]

Stage = Literal["T1", "T2", "T3", "T4", "T5", "T6"]
PayloadType = Literal[
    "case_envelope",
    "order_facts",
    "customer_context",
    "payment_reconciliation",
    "delivery_analysis",
    "verdict",
    "candidate_output",
    "validation_result",
]


class SelfCheck(StrictModel):
    nulls_handled: bool = False
    rounding_applied: bool = False
    schema_validated: bool = False


class CaseEnvelopePayload(StrictModel):
    case_id: str
    claimed_order_id: OrderId
    investigation_scope: InvestigationScope
    policy_version: PolicyVersion


class OrderItemFact(StrictModel):
    order_id: OrderId
    order_item_id: int = Field(ge=1)
    product_id: ProductId
    seller_id: SellerId
    shipping_limit_at: TimestampStr | None = None
    price_brl: float = Field(ge=0)
    freight_value_brl: float = Field(ge=0)
    category_name: str | None = None


class SellerFact(StrictModel):
    seller_id: SellerId
    shipping_limit_at: TimestampStr | None = None


class OrderFacts(StrictModel):
    order_id: OrderId
    customer_id: CustomerId | None = None
    order_status: str | None = None
    order_purchase_at: TimestampStr | None = None
    order_approved_at: TimestampStr | None = None
    order_delivered_carrier_at: TimestampStr | None = None
    order_delivered_customer_at: TimestampStr | None = None
    order_estimated_delivery_at: TimestampStr | None = None
    has_items: bool
    items: list[OrderItemFact] = Field(default_factory=list, max_length=5)
    seller_ids: list[SellerId] = Field(default_factory=list, max_length=3)
    product_ids: list[ProductId] = Field(default_factory=list, max_length=5)
    category_names: list[str] = Field(default_factory=list, max_length=5)
    seller_shipping_limits: list[SellerFact] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def items_match_flag(self) -> "OrderFacts":
        if self.has_items and not self.items:
            raise ValueError("has_items=true requires at least one item")
        if not self.has_items and self.items:
            raise ValueError("has_items=false requires an empty items list")
        return self


class CustomerContext(StrictModel):
    customer_unique_id: str | None = None
    related_order_ids: list[OrderId] = Field(default_factory=list, max_length=5)


class SellerHandoffAnalysis(StrictModel):
    seller_id: SellerId
    shipping_limit_at: TimestampStr | None = None
    handoff_variance_hours: float | None = None
    late_handoff: bool

    @model_validator(mode="after")
    def missing_handoff_is_not_late(self) -> "SellerHandoffAnalysis":
        if self.handoff_variance_hours is None and self.late_handoff:
            raise ValueError("late_handoff cannot be true when handoff variance is null")
        return self


class DeliveryAnalysis(StrictModel):
    delivered_at: TimestampStr | None = None
    estimated_delivery_at: TimestampStr | None = None
    carrier_handoff_at: TimestampStr | None = None
    delivery_variance_hours: float | None = None
    seller_handoff_analysis: list[SellerHandoffAnalysis] = Field(default_factory=list, max_length=3)
    late_handoff_seller_ids: list[SellerId] = Field(default_factory=list, max_length=3)


class PaymentReconciliation(StrictModel):
    currency: Currency = "BRL"
    item_total_brl: float | None = Field(default=None, ge=0)
    freight_total_brl: float | None = Field(default=None, ge=0)
    expected_total_brl: float | None = Field(default=None, ge=0)
    payment_total_brl: float = Field(ge=0)
    difference_brl: float | None = None
    reconciled: bool | None = None
    payment_types: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def null_reconciliation_is_consistent(self) -> "PaymentReconciliation":
        nullable = [self.item_total_brl, self.freight_total_brl, self.expected_total_brl, self.difference_brl, self.reconciled]
        if any(value is None for value in nullable) and any(value is not None for value in nullable):
            raise ValueError("item/freight/expected/difference/reconciled must be all null or all present")
        return self


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


class CaseAssessment(StrictModel):
    primary_issue: PrimaryIssue
    secondary_issues: list[SecondaryIssue] = Field(default_factory=list, max_length=5)
    case_status: CaseStatus
    confidence: float = Field(ge=0, le=1)


class AffectedEntities(StrictModel):
    order_ids: list[OrderId] = Field(default_factory=list, max_length=5)
    item_ids: list[str] = Field(default_factory=list, max_length=5)
    seller_ids: list[SellerId] = Field(default_factory=list, max_length=3)
    payment_ids: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("item_ids")
    @classmethod
    def validate_item_ids(cls, values: list[str]) -> list[str]:
        for value in values:
            if len(value.split(":")) != 2:
                raise ValueError(f"invalid item id: {value}")
        return values

    @field_validator("payment_ids")
    @classmethod
    def validate_payment_ids(cls, values: list[str]) -> list[str]:
        for value in values:
            if len(value.split(":")) != 2:
                raise ValueError(f"invalid payment id: {value}")
        return values


class ProductContext(StrictModel):
    product_ids: list[ProductId] = Field(default_factory=list, max_length=5)
    category_names: list[str] = Field(default_factory=list, max_length=5)


class ResponsibleParty(StrictModel):
    party_type: PartyType
    party_id: str


class RankedCause(StrictModel):
    cause_code: CauseCode
    rank: int = Field(ge=1, le=3)


class RootCauseAnalysis(StrictModel):
    ranked_causes: list[RankedCause] = Field(default_factory=list, max_length=3)
    responsible_parties: list[ResponsibleParty] = Field(default_factory=list, max_length=3)


class FinancialResolution(StrictModel):
    currency: Currency = "BRL"
    recommended_refund_brl: float = Field(ge=0)


class Verdict(StrictModel):
    case_assessment: CaseAssessment
    root_cause_analysis: RootCauseAnalysis
    financial_resolution: FinancialResolution
    resolution_actions: list[ResolutionAction] = Field(default_factory=list, min_length=1, max_length=5)


class CandidateOutput(StrictModel):
    case_id: str
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
    def validate_evidence_ids(cls, values: list[str]) -> list[str]:
        for value in values:
            parts = value.split(":")
            kind = parts[0]
            valid = (
                (kind == "order" and len(parts) == 2)
                or (kind == "item" and len(parts) == 3)
                or (kind == "payment" and len(parts) == 3)
                or (kind == "seller" and len(parts) == 2)
                or (kind == "policy" and len(parts) == 2)
            )
            if not valid:
                raise ValueError(f"invalid evidence id: {value}")
        return values

    @model_validator(mode="after")
    def refund_matches_status(self) -> "CandidateOutput":
        should_act = self.financial_resolution.recommended_refund_brl > 0
        expected = "action_required" if should_act else "no_action"
        if self.case_assessment.case_status != expected:
            raise ValueError("case_status must match whether recommended_refund_brl is positive")
        return self


class Violation(StrictModel):
    field_path: str
    message: str
    blamed_agent: AgentName
    severity: Literal["error", "warning"] = "error"


class ValidationResult(StrictModel):
    status: Literal["pass", "fail"]
    violations: list[Violation] = Field(default_factory=list)

    @model_validator(mode="after")
    def status_matches_violations(self) -> "ValidationResult":
        if self.status == "pass" and self.violations:
            raise ValueError("pass validation cannot include violations")
        if self.status == "fail" and not self.violations:
            raise ValueError("fail validation requires at least one violation")
        return self


EnvelopePayload = (
    CaseEnvelopePayload
    | OrderFacts
    | CustomerContext
    | PaymentReconciliation
    | DeliveryAnalysis
    | Verdict
    | CandidateOutput
    | ValidationResult
)


class A2AEnvelope(StrictModel):
    envelope_id: str = Field(min_length=1)
    case_id: str
    from_agent: AgentName
    to_agent: AgentName
    stage: Stage
    produced_at: IsoTimestampStr
    payload_type: PayloadType
    payload: EnvelopePayload
    provenance: list[str] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    self_check: SelfCheck = Field(default_factory=SelfCheck)
    model: str = Field(min_length=1)

    @model_validator(mode="after")
    def payload_type_matches_payload(self) -> "A2AEnvelope":
        expected: dict[type[BaseModel], PayloadType] = {
            CaseEnvelopePayload: "case_envelope",
            OrderFacts: "order_facts",
            CustomerContext: "customer_context",
            PaymentReconciliation: "payment_reconciliation",
            DeliveryAnalysis: "delivery_analysis",
            Verdict: "verdict",
            CandidateOutput: "candidate_output",
            ValidationResult: "validation_result",
        }
        actual = expected.get(type(self.payload))
        if actual != self.payload_type:
            raise ValueError(f"payload_type={self.payload_type} does not match {type(self.payload).__name__}")
        return self


def utc_now_z() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
