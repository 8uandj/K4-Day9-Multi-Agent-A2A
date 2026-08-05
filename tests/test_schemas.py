import json

from ec_dispute.paths import INPUT_DIR
from ec_dispute.schemas import CaseInput


def test_case_input_schema_accepts_ec_001() -> None:
    with (INPUT_DIR / "EC_001.json").open(encoding="utf-8") as file:
        payload = json.load(file)

    case = CaseInput.model_validate(payload)

    assert case.case_id == "EC_001"
    assert case.policy_version == "EC_POLICY_V2"
