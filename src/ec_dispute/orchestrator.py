"""Wave scheduling, the T3 barrier, and the repair loop.

OWNER: Thanh vien 1 (Decision & Control)

Wave 1: A1. Wave 2: A2/A3/A4 in parallel. Barrier: A5 does not start until all four
artifacts exist - running policy on a partial fact set fails silently and wrongly.
Wave 3: A5 -> A6 -> A7, with at most 2 repair rounds before deterministic fallback.
"""

from __future__ import annotations

from ec_dispute.contracts import CandidateOutput, CaseInput


async def run_case(case: CaseInput) -> CandidateOutput:
    raise NotImplementedError("TODO(TV1)")
