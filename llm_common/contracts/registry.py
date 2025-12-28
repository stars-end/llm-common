from __future__ import annotations

import json
from importlib import resources
from typing import Any

_CONTRACT_FILES: dict[str, str] = {
    "evidence.v1": "schemas/evidence.v1.json",
    "evidence_envelope.v1": "schemas/evidence_envelope.v1.json",
    "tool_result.v1": "schemas/tool_result.v1.json",
}


def list_contracts() -> list[str]:
    return sorted(_CONTRACT_FILES.keys())


def get_contract_schema(contract: str) -> dict[str, Any]:
    if contract not in _CONTRACT_FILES:
        raise KeyError(f"Unknown contract: {contract}. Known: {', '.join(list_contracts())}")

    rel_path = _CONTRACT_FILES[contract]
    package = "llm_common.contracts"
    schema_text = resources.files(package).joinpath(rel_path).read_text(encoding="utf-8")
    return json.loads(schema_text)

