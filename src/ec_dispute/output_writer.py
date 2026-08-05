"""The only module allowed to write into ``output/``.

Least privilege from docs/architecture.md section 4: a candidate that has not passed A7
never reaches disk. Keeping the write behind one function makes that enforceable.
"""

from __future__ import annotations

import json

from ec_dispute.contracts import CandidateOutput, ValidationResult
from ec_dispute.paths import OUTPUT_DIR


def write_output(candidate: CandidateOutput, validation: ValidationResult) -> None:
    """Persist a verified case. Raises when the verifier did not pass it."""
    if validation.status != "pass":
        raise PermissionError(f"{candidate.case_id} failed verification; refusing to write: {validation.violations}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{candidate.case_id}.json"
    path.write_text(
        json.dumps(candidate.to_output_json(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def written_case_ids() -> list[str]:
    return sorted(p.stem for p in OUTPUT_DIR.glob("EC_*.json"))


def missing_case_ids() -> list[str]:
    """Submission gate: the zip must hold exactly EC_001..EC_050."""
    expected = {f"EC_{i:03d}" for i in range(1, 51)}
    return sorted(expected - set(written_case_ids()))
