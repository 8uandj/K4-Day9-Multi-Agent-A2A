"""A7 verification gate - the only path to output/.

OWNER: Thanh vien 1 (Decision & Control)

Six check groups (docs/architecture.md section 3): schema, id existence, array limits,
null rules, internal consistency, timestamp format. Violations carry blamed_agent so A0
can re-dispatch the right agent instead of retrying the whole case.
"""

from __future__ import annotations

from pydantic import ValidationError

from ec_dispute.contracts import A2AEnvelope, CandidateOutput, ValidationResult, Violation, unsupported_evidence
from ec_dispute.data_store import DataStore


def verify(candidate: CandidateOutput, upstream: list[A2AEnvelope], store: DataStore) -> ValidationResult:
    violations: list[Violation] = []

    def add(field_path: str, message: str, blamed_agent: str = "A6_evidence") -> None:
        violations.append(Violation(field_path=field_path, message=message, blamed_agent=blamed_agent))

    try:
        # Re-validate from JSON-shaped data so this gate also protects callers that built
        # CandidateOutput through model_construct or deserialised untrusted JSON.
        candidate = CandidateOutput.model_validate(candidate.to_output_json())
    except ValidationError as exc:
        for error in exc.errors():
            path = ".".join(str(part) for part in error["loc"]) or "$"
            add(path, error["msg"])
        return ValidationResult(status="fail", violations=violations)

    provenance: list[str] = []
    for envelope in upstream:
        provenance.extend(envelope.provenance)

    for evidence_id in unsupported_evidence(candidate.evidence_ids, provenance):
        add("evidence_ids", f"{evidence_id!r} is not backed by upstream provenance")

    for evidence_id in candidate.evidence_ids:
        if evidence_id.startswith("policy:"):
            continue
        try:
            exists = store.key_exists(evidence_id)
        except NotImplementedError:
            raise
        except Exception as exc:
            add("evidence_ids", f"could not verify {evidence_id!r}: {exc}")
            continue
        if not exists:
            add("evidence_ids", f"{evidence_id!r} does not exist in the key index")

    for product_id in candidate.product_context.product_ids:
        reference = f"product:{product_id}"
        try:
            exists = store.key_exists(reference)
        except NotImplementedError:
            raise
        except Exception as exc:
            add("product_context.product_ids", f"could not verify {reference!r}: {exc}")
            continue
        if not exists:
            add("product_context.product_ids", f"{reference!r} does not exist in the key index")

    return ValidationResult(status="fail" if violations else "pass", violations=violations)
