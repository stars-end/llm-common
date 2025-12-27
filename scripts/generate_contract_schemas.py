#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from llm_common.agents.provenance import Evidence, EvidenceEnvelope
from llm_common.agents.tools import ToolResult


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    out_dir = Path(__file__).resolve().parents[1] / "llm_common" / "contracts" / "schemas"

    evidence_schema = Evidence.model_json_schema()
    evidence_schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    evidence_schema["$id"] = "https://github.com/stars-end/llm-common/contracts/evidence.v1.json"
    _write_json(out_dir / "evidence.v1.json", evidence_schema)

    envelope_schema = EvidenceEnvelope.model_json_schema()
    envelope_schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    envelope_schema["$id"] = "https://github.com/stars-end/llm-common/contracts/evidence_envelope.v1.json"
    _write_json(out_dir / "evidence_envelope.v1.json", envelope_schema)

    tool_result_schema = TypeAdapter(ToolResult).json_schema()
    tool_result_schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    tool_result_schema["$id"] = "https://github.com/stars-end/llm-common/contracts/tool_result.v1.json"
    _write_json(out_dir / "tool_result.v1.json", tool_result_schema)


if __name__ == "__main__":
    main()

