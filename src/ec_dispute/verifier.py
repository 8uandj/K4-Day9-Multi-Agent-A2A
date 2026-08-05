"""A7 verification gate - the only path to output/.

OWNER: Thanh vien 1 (Decision & Control)

Six check groups (docs/architecture.md section 3): schema, id existence, array limits,
null rules, internal consistency, timestamp format. Violations carry blamed_agent so A0
can re-dispatch the right agent instead of retrying the whole case.
"""

from __future__ import annotations

from ec_dispute.contracts import A2AEnvelope, CandidateOutput, ValidationResult
from ec_dispute.data_store import DataStore


def verify(candidate: CandidateOutput, upstream: list[A2AEnvelope], store: DataStore) -> ValidationResult:
    raise NotImplementedError("TODO(TV1)")
