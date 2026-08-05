"""A6 — evidence ids and final assembly.

OWNER: Thanh vien 2 (Data & Entities)

The last agent before the verification gate. It has NO data access at all (access matrix,
docs/architecture.md section 4): every id it writes must already appear in an upstream
artifact, so a fabricated entity has no route into ``output/``.

This is also where ``contracts.LIMITS`` finally applies. Upstream facts stay complete —
truncating them would corrupt A3's payment totals — so all capping happens here, at the
boundary where the graded arrays are actually produced.
"""

from __future__ import annotations

from ec_dispute.agents.base import Agent
from ec_dispute.contracts import (
    LIMITS,
    A2AEnvelope,
    AffectedEntities,
    CandidateOutput,
    CustomerContext,
    DeliveryAnalysis,
    OrderFacts,
    PaymentReconciliation,
    ProductContext,
    SelfCheck,
    Verdict,
    item_entity_id,
    item_evidence_id,
    order_evidence_id,
    payment_entity_id,
    payment_evidence_id,
    policy_evidence_id,
    seller_evidence_id,
)


def payment_sequentials_from_provenance(order_id: str, provenance: list[str]) -> list[int]:
    """Recover ``payment_sequential`` values from what A3 declared it read.

    ``PaymentReconciliation`` is a graded output section and carries totals only, so the
    sequentials reach A6 through the provenance channel — which is exactly what provenance
    is for: the record of which rows an agent actually touched. Requires A3 to list
    ``payment:<order_id>:<seq>`` for every payment row it summed.
    """
    prefix = f"payment:{order_id}:"
    sequentials = {int(ref[len(prefix):]) for ref in provenance if ref.startswith(prefix)}
    return sorted(sequentials)


class EvidenceAgent(Agent):
    name = "A6_evidence"
    #: No lookup tools. A6 reads artifacts, never data.
    allowed_tools = ("assemble_output",)

    def assemble(
        self,
        case_id: str,
        facts: OrderFacts,
        customer: CustomerContext,
        delivery: DeliveryAnalysis,
        payment: PaymentReconciliation,
        verdict: Verdict,
        upstream_provenance: list[str],
    ) -> CandidateOutput:
        order_id = facts.order_id
        sequentials = payment_sequentials_from_provenance(order_id, upstream_provenance)
        if payment.payment_total_brl > 0 and not sequentials:
            # Fail loudly and name the culprit rather than ship an empty payment_ids array.
            raise ValueError(
                f"{case_id}: payment_total is {payment.payment_total_brl} but A3 declared no "
                f"'payment:{order_id}:<seq>' provenance; payment_ids cannot be built"
            )

        items = facts.items[: LIMITS["item_ids"]]
        seller_ids = facts.seller_ids[: LIMITS["seller_ids"]]
        capped_sequentials = sequentials[: LIMITS["payment_ids"]]

        responsible_sellers = [
            party.party_id
            for party in verdict.root_cause_analysis.responsible_parties
            if party.party_type == "seller"
        ]

        entities = AffectedEntities(
            order_ids=[order_id],
            item_ids=[item_entity_id(order_id, item.order_item_id) for item in items],
            seller_ids=seller_ids,
            payment_ids=[payment_entity_id(order_id, seq) for seq in capped_sequentials],
        )

        return CandidateOutput(
            case_id=case_id,
            case_assessment=verdict.case_assessment,
            affected_entities=entities,
            customer_context=customer,
            product_context=ProductContext(
                product_ids=facts.product_ids[: LIMITS["product_ids"]],
                category_names=facts.category_names[: LIMITS["category_names"]],
            ),
            delivery_analysis=delivery,
            payment_reconciliation=payment,
            root_cause_analysis=verdict.root_cause_analysis,
            evidence_ids=self.build_evidence(order_id, items, capped_sequentials, responsible_sellers, verdict),
            financial_resolution=verdict.financial_resolution,
            resolution_actions=list(verdict.resolution_actions),
        )

    @staticmethod
    def build_evidence(
        order_id: str,
        items: list,
        payment_sequentials: list[int],
        responsible_sellers: list[str],
        verdict: Verdict,
    ) -> list[str]:
        """README section 5: the order, its items, its payments, the responsible seller if
        any, and the matching policy.

        The order and policy citations are mandatory (the contract rejects output without
        them), so they get reserved slots before the budget is spent on the middle.
        """
        causes = verdict.root_cause_analysis.ranked_causes
        head = [order_evidence_id(order_id)]
        tail = [policy_evidence_id(causes[0].cause_code)] if causes else []

        middle = [item_evidence_id(order_id, item.order_item_id) for item in items]
        middle += [payment_evidence_id(order_id, seq) for seq in payment_sequentials]
        middle += [seller_evidence_id(seller_id) for seller_id in responsible_sellers]

        budget = LIMITS["evidence_ids"] - len(head) - len(tail)
        return head + middle[:budget] + tail

    def run(
        self,
        case_id: str,
        facts: OrderFacts,
        customer: CustomerContext,
        delivery: DeliveryAnalysis,
        payment: PaymentReconciliation,
        verdict: Verdict,
        upstream_provenance: list[str],
        *,
        to_agent: str = "A7_verifier",
        attempt: int = 0,
    ) -> A2AEnvelope:  # noqa: D401
        """Emit ``candidate_output`` at T5, carrying the merged provenance forward to A7."""
        candidate = self.assemble(case_id, facts, customer, delivery, payment, verdict, upstream_provenance)
        return self.emit(
            case_id=case_id,
            to_agent=to_agent,
            stage="T5",
            payload_type="candidate_output",
            payload=candidate,
            # A7 checks evidence against the union of everything upstream actually read.
            provenance=sorted(set(upstream_provenance)),
            tool_calls=["assemble_output"],
            self_check=SelfCheck(nulls_handled=True, rounding_applied=True, schema_validated=True),
            attempt=attempt,
        )


def assemble_candidate_output(
    case_id: str,
    facts: OrderFacts,
    customer: CustomerContext,
    payment: PaymentReconciliation,
    delivery: DeliveryAnalysis,
    verdict: Verdict,
    provenance: list[str] | None = None,
    payment_sequentials: list[int] | None = None,
) -> CandidateOutput:
    """Function-style entry point used by ``orchestrator.run_case`` (TV1).

    Note the argument order — ``payment`` before ``delivery`` — matching the orchestrator's
    existing call. The class-based :meth:`EvidenceAgent.assemble` keeps the artifact order
    used elsewhere.

    ``affected_entities.payment_ids`` needs the ``payment_sequential`` of every payment row,
    which ``PaymentReconciliation`` does not carry (it is a graded section holding totals
    only). Supply one of:

    * ``provenance`` — the merged upstream provenance, containing A3's
      ``payment:<order_id>:<seq>`` entries. This is the intended path.
    * ``payment_sequentials`` — the raw sequentials, when the caller has them to hand.
    """
    if payment_sequentials is not None:
        provenance = list(provenance or []) + [
            payment_evidence_id(facts.order_id, seq) for seq in payment_sequentials
        ]
    return EvidenceAgent().assemble(
        case_id, facts, customer, delivery, payment, verdict, list(provenance or [])
    )
