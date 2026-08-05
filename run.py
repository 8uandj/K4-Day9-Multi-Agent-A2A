"""Entry point: run every case and write output/ + logging/.

    python run.py                # all 50 cases
    python run.py EC_001 EC_002   # a subset while developing
"""

from __future__ import annotations

import argparse
import asyncio
import json

from ec_dispute.contracts import CaseInput
from ec_dispute.orchestrator import run_case
from ec_dispute.paths import INPUT_DIR
from ec_dispute import trace


def load_cases(case_ids: list[str] | None) -> list[CaseInput]:
    paths = sorted(INPUT_DIR.glob("EC_*.json"))
    if case_ids:
        wanted = set(case_ids)
        paths = [p for p in paths if p.stem in wanted]
    return [CaseInput.model_validate(json.loads(p.read_text(encoding="utf-8"))) for p in paths]


async def main_async(case_ids: list[str] | None) -> None:
    cases = load_cases(case_ids)
    trace.start_run()
    for case in cases:
        await run_case(case, write=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="EC_POLICY_V2 multi-agent dispute resolution")
    parser.add_argument("case_ids", nargs="*", help="optional subset, e.g. EC_001 EC_002")
    args = parser.parse_args()
    asyncio.run(main_async(args.case_ids or None))


if __name__ == "__main__":
    main()
