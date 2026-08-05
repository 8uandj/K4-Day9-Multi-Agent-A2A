"""FROZEN CONTRACT — A2A transport: case input, artifact payloads, handoff envelope.

Everything that moves *between* agents lives here. What the grader reads lives in
``output_schema.py``; this module imports from it and never the other way round.

FREEZE RULES — same as ``output_schema.py``: no solo edits, and a rejected envelope
means the sender is wrong, not the contract.

Two properties this file buys the team:

1. **Payload type drives parsing.** ``payload`` is resolved from ``payload_type``, not by
   letting Pydantic guess a union member. An artifact can never be silently parsed as the
   wrong model.
2. **Provenance and evidence share one grammar.** ``A7`` can then check
   ``evidence_ids ⊆ provenance`` by plain set containment. An id that no agent ever read
   from a CSV cannot reach ``output/``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ec_dispute.contracts.output_schema import (
    CaseId,
    CustomerContext,
    DeliveryAnalysis,
    OlistId,
    OrderStatus,
    PaymentReconciliation,
    StrictModel,
    TimestampStr,
    Verdict,
    CandidateOutput,
    Money2,
    validate_reference,
)

CONTRACT_VERSION = "1.0.0-frozen"

# --------------------------------------------------------------------------------------
# Ingress — input/EC_*.json
# --------------------------------------------------------------------------------------

PolicyVersion = Literal["EC_POLICY_V2"]


class CustomerRequest(StrictModel):
    language: str = Field(default="vi", min_length=2)
    message: str = Field(min_length=1)
    claimed_order_id: OlistId


class InvestigationScope(StrictModel):
    include_customer_history: bool = True
    include_product_context: bool = True


class CaseInput(StrictModel):
    case_id: CaseId
    customer_request: CustomerRequest
    investigation_scope: InvestigationScope
    policy_version: PolicyVersion


# --------------------------------------------------------------------------------------
# Agents, stages, payload types
# --------------------------------------------------------------------------------------

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

COORDINATOR: AgentName = "A0_coordinator"


class SelfCheck(StrictModel):
    """Sender's own attestation. Cheap, and it makes a lazy agent visible in the trace."""

    nulls_handled: bool = False
    rounding_applied: bool = False
    schema_validated: bool = False


# --------------------------------------------------------------------------------------
# Artifact payloads
# --------------------------------------------------------------------------------------


class CaseEnvelopePayload(StrictModel):
    """T1 — A0 hands the case to A1. Deliberately carries no CSV data."""

    case_id: CaseId
    claimed_order_id: OlistId
    investigation_scope: InvestigationScope
    policy_version: PolicyVersion


class OrderItemFact(StrictModel):
    order_id: OlistId
    order_item_id: int = Field(ge=1)
    product_id: OlistId
    seller_id: OlistId
    shipping_limit_at: TimestampStr | None = None
    price_brl: Money2
    freight_value_brl: Money2
    category_name: str | None = None


class SellerFact(StrictModel):
    """Per-seller binding deadline: the EARLIEST shipping_limit_date across that seller's items."""

    seller_id: OlistId
    shipping_limit_at: TimestampStr | None = None


class OrderFacts(StrictModel):
    """T2/T3 — A1's fact base. The root of every downstream number.

    Note the absence of ``max_length`` on the lists. Output arrays are capped at 5/5/3, but
    facts must stay COMPLETE: A3 sums ``price_brl`` over every item to reconcile payments,
    so truncating here would silently corrupt the totals. Truncation belongs to A6 at
    assembly time, where ``output_schema.LIMITS`` applies.
    """

    order_id: OlistId
    customer_id: OlistId | None = None
    order_status: OrderStatus | None = None
    order_purchase_at: TimestampStr | None = None
    order_approved_at: TimestampStr | None = None
    order_delivered_carrier_at: TimestampStr | None = None
    order_delivered_customer_at: TimestampStr | None = None
    order_estimated_delivery_at: TimestampStr | None = None
    has_items: bool
    items: list[OrderItemFact] = Field(default_factory=list)
    seller_ids: list[OlistId] = Field(default_factory=list)
    product_ids: list[OlistId] = Field(default_factory=list)
    category_names: list[str] = Field(default_factory=list)
    seller_shipping_limits: list[SellerFact] = Field(default_factory=list)

    @model_validator(mode="after")
    def flag_matches_items(self) -> "OrderFacts":
        if self.has_items != bool(self.items):
            raise ValueError(f"has_items={self.has_items} contradicts {len(self.items)} item rows")
        if not self.has_items and (self.seller_ids or self.product_ids or self.category_names):
            # README section 4: no item row -> item, seller, product, category stay empty.
            raise ValueError("an order with no item rows must report empty seller/product/category lists")
        derived = {item.seller_id for item in self.items}
        if set(self.seller_ids) != derived:
            raise ValueError("seller_ids must be exactly the distinct sellers appearing in items")
        return self


class Violation(StrictModel):
    field_path: str = Field(min_length=1)
    message: str = Field(min_length=1)
    blamed_agent: AgentName
    severity: Literal["error", "warning"] = "error"


class ValidationResult(StrictModel):
    """T6 — A7's verdict on a candidate output, and the routing hint for a repair round."""

    status: Literal["pass", "fail"]
    violations: list[Violation] = Field(default_factory=list)
    repair_round: int = Field(default=0, ge=0, le=2)

    @model_validator(mode="after")
    def status_matches_violations(self) -> "ValidationResult":
        errors = [v for v in self.violations if v.severity == "error"]
        if self.status == "pass" and errors:
            raise ValueError("a passing result cannot carry error-severity violations")
        if self.status == "fail" and not errors:
            raise ValueError("a failing result needs at least one error-severity violation")
        return self

    @property
    def blamed_agents(self) -> list[AgentName]:
        """Agents A0 must re-dispatch, in first-seen order."""
        seen: list[AgentName] = []
        for violation in self.violations:
            if violation.severity == "error" and violation.blamed_agent not in seen:
                seen.append(violation.blamed_agent)
        return seen


# --------------------------------------------------------------------------------------
# Routing table — §5.3 of docs/architecture.md, enforced
# --------------------------------------------------------------------------------------

PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "case_envelope": CaseEnvelopePayload,
    "order_facts": OrderFacts,
    "customer_context": CustomerContext,
    "payment_reconciliation": PaymentReconciliation,
    "delivery_analysis": DeliveryAnalysis,
    "verdict": Verdict,
    "candidate_output": CandidateOutput,
    "validation_result": ValidationResult,
}

#: Exactly one agent may author each payload type. This is what makes provenance meaningful.
PAYLOAD_PRODUCER: dict[str, AgentName] = {
    "case_envelope": "A0_coordinator",
    "order_facts": "A1_order_product",
    "customer_context": "A2_customer",
    "payment_reconciliation": "A3_payment",
    "delivery_analysis": "A4_delivery",
    "verdict": "A5_policy",
    "candidate_output": "A6_evidence",
    "validation_result": "A7_verifier",
}

#: ``order_facts`` legitimately travels twice: T2 to the wave-2 agents, T3 on to A5.
PAYLOAD_STAGES: dict[str, tuple[str, ...]] = {
    "case_envelope": ("T1",),
    "order_facts": ("T2", "T3"),
    "customer_context": ("T3",),
    "payment_reconciliation": ("T3",),
    "delivery_analysis": ("T3",),
    "verdict": ("T4",),
    "candidate_output": ("T5",),
    "validation_result": ("T6",),
}

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

IsoTimestampStr = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")]


def utc_now_z() -> str:
    """Timezone-aware UTC stamp for the transport layer only.

    Graded timestamps keep the CSV format (``YYYY-MM-DD HH:MM:SS``) and are never produced here.
    """
    return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z"


def build_envelope_id(case_id: str, stage: str, from_agent: str, attempt: int = 0) -> str:
    """``EC_001#T3#A4_delivery`` — plus ``#r1`` on a repair round, so retries stay distinguishable."""
    suffix = f"#r{attempt}" if attempt else ""
    return f"{case_id}#{stage}#{from_agent}{suffix}"


class A2AEnvelope(StrictModel):
    """One handoff. Validated identically by sender and receiver."""

    envelope_id: str = Field(min_length=1)
    case_id: CaseId
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

    @model_validator(mode="before")
    @classmethod
    def parse_payload_by_type(cls, data: object) -> object:
        """Resolve ``payload`` through ``payload_type`` instead of guessing a union member."""
        if not isinstance(data, dict):
            return data
        payload_type = data.get("payload_type")
        payload = data.get("payload")
        if isinstance(payload, dict) and payload_type in PAYLOAD_MODELS:
            return {**data, "payload": PAYLOAD_MODELS[payload_type].model_validate(payload)}
        return data

    @field_validator("provenance")
    @classmethod
    def well_formed_provenance(cls, values: list[str]) -> list[str]:
        for value in values:
            validate_reference(value, allow_provenance_kinds=True)
        return values

    @model_validator(mode="after")
    def routing_is_legal(self) -> "A2AEnvelope":
        expected_model = PAYLOAD_MODELS[self.payload_type]
        if type(self.payload) is not expected_model:
            raise ValueError(f"payload_type={self.payload_type!r} does not match {type(self.payload).__name__}")

        producer = PAYLOAD_PRODUCER[self.payload_type]
        # A0 is the blackboard: it may relay another agent's artifact onward unchanged.
        if self.from_agent not in (producer, COORDINATOR):
            raise ValueError(f"{self.payload_type!r} may only be sent by {producer} or {COORDINATOR}")
        if self.stage not in PAYLOAD_STAGES[self.payload_type]:
            raise ValueError(f"{self.payload_type!r} belongs to stage {PAYLOAD_STAGES[self.payload_type]}, got {self.stage}")
        if self.from_agent == self.to_agent:
            raise ValueError("an agent cannot hand off to itself")
        if not self.envelope_id.startswith(f"{self.case_id}#"):
            raise ValueError(f"envelope_id must start with '{self.case_id}#', got {self.envelope_id!r}")

        payload_case_id = getattr(self.payload, "case_id", None)
        if payload_case_id is not None and payload_case_id != self.case_id:
            raise ValueError(f"payload case_id {payload_case_id!r} does not match envelope {self.case_id!r}")
        return self


def unsupported_evidence(evidence_ids: list[str], provenance: list[str]) -> list[str]:
    """Evidence ids that no upstream agent ever read. A7's fabrication check.

    Returns the offending ids, empty list when every citation is backed by a real read.
    ``policy:`` citations are exempt: they come from the EC_POLICY_V2 table, not a CSV row,
    so no agent can list them as provenance.
    """
    seen = set(provenance)
    return [eid for eid in evidence_ids if not eid.startswith("policy:") and eid not in seen]
