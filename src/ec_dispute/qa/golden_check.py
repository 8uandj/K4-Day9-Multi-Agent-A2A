"""Regression harness: reproducibility and submission gates.

OWNER: Thanh vien 3 (Analysis)

A re-run must produce byte-identical files. If it does not, something non-deterministic
leaked into the pipeline and the run cannot be trusted.
"""

from __future__ import annotations

from ec_dispute.output_writer import missing_case_ids


def assert_submission_complete() -> None:
    missing = missing_case_ids()
    if missing:
        raise AssertionError(f"missing outputs: {missing}")


def assert_rerun_is_identical(before: dict[str, str], after: dict[str, str]) -> None:
    for case_id, content in before.items():
        if case_id not in after:
            raise AssertionError(f"Missing case in rerun: {case_id}")
        if content != after[case_id]:
            raise AssertionError(f"Case {case_id} is not byte-identical between runs")
    
    for case_id in after:
        if case_id not in before:
            raise AssertionError(f"Unexpected extra case in rerun: {case_id}")
