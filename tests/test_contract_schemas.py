from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter

from llm_common.agents.executor import StreamEvent
from llm_common.agents.provenance import Evidence, EvidenceEnvelope
from llm_common.agents.tools import ToolResult
from llm_common.contracts import get_contract_schema
from llm_common.models import AdvisorRequest, AdvisorResponse


def test_contract_registry_loads() -> None:
    assert get_contract_schema("advisor_request.v1")["title"] == "AdvisorRequest"
    assert get_contract_schema("advisor_response.v1")["title"] == "AdvisorResponse"
    assert get_contract_schema("evidence.v1")["title"] == "Evidence"
    assert get_contract_schema("evidence_envelope.v1")["title"] == "EvidenceEnvelope"
    assert get_contract_schema("stream_event.v1")["title"] == "StreamEvent"
    assert get_contract_schema("tool_result.v1")["title"] == "ToolResult"


def test_contract_files_exist() -> None:
    base = Path(__file__).resolve().parents[1] / "llm_common" / "contracts" / "schemas"
    assert (base / "advisor_request.v1.json").exists()
    assert (base / "advisor_response.v1.json").exists()
    assert (base / "evidence.v1.json").exists()
    assert (base / "evidence_envelope.v1.json").exists()
    assert (base / "stream_event.v1.json").exists()
    assert (base / "tool_result.v1.json").exists()


def test_contract_matches_models_snapshot() -> None:
    advisor_request = get_contract_schema("advisor_request.v1")
    advisor_response = get_contract_schema("advisor_response.v1")
    evidence = get_contract_schema("evidence.v1")
    envelope = get_contract_schema("evidence_envelope.v1")
    stream_event = get_contract_schema("stream_event.v1")
    tool_result = get_contract_schema("tool_result.v1")

    expected_advisor_request = AdvisorRequest.model_json_schema()
    expected_advisor_request["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    expected_advisor_request["$id"] = "https://github.com/stars-end/llm-common/contracts/advisor_request.v1.json"

    expected_advisor_response = AdvisorResponse.model_json_schema()
    expected_advisor_response["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    expected_advisor_response["$id"] = "https://github.com/stars-end/llm-common/contracts/advisor_response.v1.json"

    expected_evidence = Evidence.model_json_schema()
    expected_evidence["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    expected_evidence["$id"] = "https://github.com/stars-end/llm-common/contracts/evidence.v1.json"

    expected_envelope = EvidenceEnvelope.model_json_schema()
    expected_envelope["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    expected_envelope["$id"] = "https://github.com/stars-end/llm-common/contracts/evidence_envelope.v1.json"

    expected_stream_event = StreamEvent.model_json_schema()
    expected_stream_event["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    expected_stream_event["$id"] = "https://github.com/stars-end/llm-common/contracts/stream_event.v1.json"

    expected_tool_result = TypeAdapter(ToolResult).json_schema()
    expected_tool_result["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    expected_tool_result["$id"] = "https://github.com/stars-end/llm-common/contracts/tool_result.v1.json"

    assert advisor_request == expected_advisor_request
    assert advisor_response == expected_advisor_response
    assert evidence == expected_evidence
    assert envelope == expected_envelope
    assert stream_event == expected_stream_event
    assert tool_result == expected_tool_result
