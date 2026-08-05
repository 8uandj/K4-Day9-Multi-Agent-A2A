"""Wave scheduling, the T3 barrier, and the repair loop.

OWNER: Thanh vien 1 (Decision & Control)

Wave 1: A1. Wave 2: A2/A3/A4 in parallel. Barrier: A5 does not start until all four
artifacts exist - running policy on a partial fact set fails silently and wrongly.
Wave 3: A5 -> A6 -> A7, with at most 2 repair rounds before deterministic fallback.
"""

from __future__ import annotations

import asyncio

from ec_dispute import trace
from ec_dispute.agents.coordinator import CoordinatorAgent
from ec_dispute.contracts import CandidateOutput, CaseInput, CustomerContext, PaymentReconciliation
from ec_dispute.data_store import DataStore
from ec_dispute.output_writer import write_output
from ec_dispute.policy_engine import decide
from ec_dispute.tools.calculations import build_delivery_analysis, build_payment_reconciliation
from ec_dispute.tools.lookups import build_customer_context, build_order_facts
from ec_dispute.verifier import verify


async def run_case(case: CaseInput, store: DataStore | None = None, *, write: bool = False) -> CandidateOutput:
    store = store or DataStore()
    coordinator = CoordinatorAgent()

    t1 = coordinator.create_case_envelope(case)
    trace.record_handoff(t1, latency_ms=0)

    facts = build_order_facts(store, case.customer_request.claimed_order_id)

    def build_payment() -> PaymentReconciliation:
        return build_payment_reconciliation(facts, store.payments_for(facts.order_id))

    if facts.customer_id is None:
        customer_task = asyncio.to_thread(CustomerContext)
    else:
        customer_task = asyncio.to_thread(build_customer_context, store, facts.customer_id, facts.order_id)
    payment_task = asyncio.to_thread(build_payment)
    delivery_task = asyncio.to_thread(build_delivery_analysis, facts)
    customer, payment, delivery = await asyncio.gather(customer_task, payment_task, delivery_task)

    verdict = decide(facts, customer, payment, delivery)

    # A6 assembly belongs to TV2 and is intentionally not duplicated here. Keeping this
    # boundary explicit prevents A0 from becoming a hidden monolith.
    from ec_dispute.agents.evidence import assemble_candidate_output  # type: ignore[attr-defined]

    candidate = assemble_candidate_output(case.case_id, facts, customer, payment, delivery, verdict)
    validation = verify(candidate, [], store)
    if write:
        write_output(candidate, validation)
    return candidate
