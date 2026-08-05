"""A/B harness: flip one interpretation at a time, regenerate output/, rebuild the zip.

    python variant.py                 # baseline, no changes
    python variant.py cat_en          # category_names in English
    python variant.py raw_types       # payment_types not deduplicated
    python variant.py multi_item_1    # multi_item_order when the order has >=1 item
    python variant.py empty_handoff   # seller_handoff_analysis=[] when carrier handoff is null
    python variant.py refund_all      # verify_refund_completion on every refund case
    python variant.py cat_en raw_types  # combine

Each run prints how many of the 50 cases the flag actually changed, so a flag that moves
nothing is never worth a submission slot.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

FLAGS = set(sys.argv[1:])

# --- apply flags before anything imports the modules they patch -------------------------
import ec_dispute.data_store as data_store  # noqa: E402
import ec_dispute.contracts.output_schema as schema  # noqa: E402

if "cat_en" in FLAGS:
    data_store.CATEGORY_NAMES_TRANSLATED = True
if "raw_types" in FLAGS:
    schema.PAYMENT_TYPES_DEDUPED = False

import ec_dispute.orchestrator as orch  # noqa: E402
import ec_dispute.policy_engine as policy  # noqa: E402
import ec_dispute.tools.calculations as calc  # noqa: E402
from ec_dispute.contracts import CaseInput, DeliveryAnalysis  # noqa: E402
from ec_dispute.data_store import DataStore  # noqa: E402
from ec_dispute.orchestrator import run_case  # noqa: E402
from ec_dispute.paths import INPUT_DIR, OUTPUT_DIR  # noqa: E402
from ec_dispute import trace  # noqa: E402

# orchestrator did `from ... import build_payment_reconciliation`, so the name must be
# rebound on the orchestrator module — patching calculations alone has no effect.
if "raw_types" in FLAGS:
    _orig_payment = orch.build_payment_reconciliation

    def _raw_types(facts, payment_rows):
        recon = _orig_payment(facts, payment_rows)
        ordered = sorted(payment_rows, key=lambda r: int(r["payment_sequential"]))
        recon.payment_types = [r["payment_type"] for r in ordered]
        return recon

    orch.build_payment_reconciliation = _raw_types
    calc.build_payment_reconciliation = _raw_types

if "multi_item_1" in FLAGS:
    _orig_secondary = policy._secondary_issues

    def _secondary(facts, customer, payment, payment_row_count=None):
        issues = _orig_secondary(facts, customer, payment, payment_row_count)
        if facts.items and "multi_item_order" not in issues:
            issues.insert(0, "multi_item_order")
        return issues

    policy._secondary_issues = _secondary

if "empty_handoff" in FLAGS:
    _orig_delivery = orch.build_delivery_analysis

    def _delivery(facts):
        analysis = _orig_delivery(facts)
        if facts.order_delivered_carrier_at is None:
            return DeliveryAnalysis(
                delivered_at=analysis.delivered_at,
                estimated_delivery_at=analysis.estimated_delivery_at,
                carrier_handoff_at=None,
                delivery_variance_hours=analysis.delivery_variance_hours,
                seller_handoff_analysis=[],
                late_handoff_seller_ids=[],
            )
        return analysis

    orch.build_delivery_analysis = _delivery
    calc.build_delivery_analysis = _delivery

if "refund_all" in FLAGS:
    _orig_actions = policy._actions

    def _actions(primary, facts, payment, payment_row_count=None):
        actions = _orig_actions(primary, facts, payment, payment_row_count)
        if policy.POLICY_RULES[primary].case_status == "action_required" and "verify_refund_completion" not in actions:
            follow = [a for a in actions[1:] if a in ("review_seller_handoff", "review_carrier_delay")]
            rest = [a for a in actions[1:] if a not in follow]
            actions = [actions[0], *follow, "verify_refund_completion", *rest]
        return actions[:5]

    policy._actions = _actions


async def main() -> None:
    before = {p.name: p.read_text(encoding="utf-8") for p in sorted(OUTPUT_DIR.glob("EC_*.json"))}

    cases = [CaseInput.model_validate(json.loads(p.read_text(encoding="utf-8")))
             for p in sorted(INPUT_DIR.glob("EC_*.json"))]
    trace.start_run()
    store = DataStore()
    for case in cases:
        await run_case(case, store=store, write=True)

    after = {p.name: p.read_text(encoding="utf-8") for p in sorted(OUTPUT_DIR.glob("EC_*.json"))}
    changed = sorted(n for n in after if before.get(n) != after[n])

    zip_path = ROOT / "submission.zip"
    zip_path.unlink(missing_ok=True)
    subprocess.run(["zip", "-q", "-X", str(zip_path), *[f"output/EC_{i:03d}.json" for i in range(1, 51)]],
                   cwd=ROOT, check=True)
    entries = subprocess.run(["unzip", "-Z1", str(zip_path)], capture_output=True, text=True).stdout.split()

    print(f"flags       : {sorted(FLAGS) or ['baseline']}")
    print(f"cases changed vs previous run: {len(changed)}  {changed[:12]}{' ...' if len(changed) > 12 else ''}")
    print(f"zip         : {zip_path.name}, {len(entries)} entries, all under output/: {all(e.startswith('output/') for e in entries)}")


if __name__ == "__main__":
    asyncio.run(main())
