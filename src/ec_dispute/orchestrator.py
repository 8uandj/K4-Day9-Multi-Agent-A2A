"""Wave scheduling, the T3 barrier, and the repair loop.

OWNER: Thanh vien 1 (Decision & Control)

Wave 1: A1. Wave 2: A2/A3/A4 in parallel. Barrier: A5 does not start until all four
artifacts exist - running policy on a partial fact set fails silently and wrongly.
Wave 3: A5 -> A6 -> A7, with at most 2 repair rounds before deterministic fallback.
"""

from __future__ import annotations

from ec_dispute import trace
from ec_dispute.agents.evidence import EvidenceAgent
from ec_dispute.agents.coordinator import CoordinatorAgent
from ec_dispute.contracts import CandidateOutput, CaseInput, CustomerContext
from ec_dispute.data_store import DataStore
from ec_dispute.output_writer import write_output
from ec_dispute.policy_engine import decide
from ec_dispute.tools.calculations import build_delivery_analysis, build_payment_reconciliation
from ec_dispute.tools.lookups import (
    build_customer_context,
    build_order_facts,
    customer_context_provenance,
    order_facts_provenance,
)
from ec_dispute.verifier import verify


async def run_case(case: CaseInput, store: DataStore | None = None, *, write: bool = False) -> CandidateOutput:
    store = store or DataStore()
    coordinator = CoordinatorAgent()

    t1 = coordinator.create_case_envelope(case)
    trace.record_handoff(t1, latency_ms=0)

    facts = build_order_facts(store, case.customer_request.claimed_order_id)

    if facts.customer_id is None:
        customer = CustomerContext()
    else:
        customer = build_customer_context(store, facts.customer_id, facts.order_id)
    payment_rows = store.payments_for(facts.order_id)
    payment = build_payment_reconciliation(facts, payment_rows)
    delivery = build_delivery_analysis(facts)

    verdict = decide(facts, customer, payment, delivery, payment_row_count=len(payment_rows))

    provenance = []
    provenance += order_facts_provenance(facts)
    if facts.customer_id:
        provenance += customer_context_provenance(facts.customer_id, customer)
    provenance += [f"payment:{facts.order_id}:{int(row['payment_sequential'])}" for row in payment_rows]

    candidate_env = EvidenceAgent().run(
        case.case_id,
        facts,
        customer,
        delivery,
        payment,
        verdict,
        provenance,
    )
    trace.record_handoff(candidate_env, latency_ms=0)
    candidate = candidate_env.payload
    validation = verify(candidate, [candidate_env], store)
    if write:
        write_output(candidate, validation)
    return candidate
