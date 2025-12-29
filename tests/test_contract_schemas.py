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


def test_schemas_are_packaged() -> None:
    """
    Verifies that the JSON schema files are included in both the sdist and wheel packages.
    """
    import shutil
    import subprocess
    import tarfile
    import zipfile

    # Define paths
    repo_root = Path(__file__).resolve().parents[1]
    dist_dir = repo_root / "dist"

    # Clean up any previous build artifacts
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    try:
        # 1. Build both sdist and wheel packages
        build_result = subprocess.run(
            ["poetry", "build"],
            check=False,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        assert build_result.returncode == 0, f"Poetry build failed: {build_result.stderr}"

        # 2. Verify the sdist package (tar.gz)
        tarballs = list(dist_dir.glob("*.tar.gz"))
        assert len(tarballs) == 1, f"Expected 1 sdist tarball, but found {len(tarballs)}."
        sdist_path = tarballs[0]
        with tarfile.open(sdist_path, "r:gz") as tar:
            sdist_members = tar.getnames()

        # The top-level dir in the tarball is named after the sdist package
        sdist_root_dir = sdist_path.name.replace(".tar.gz", "")
        expected_sdist_schemas = [
            f"{sdist_root_dir}/llm_common/contracts/schemas/{p.name}"
            for p in (repo_root / "llm_common" / "contracts" / "schemas").glob("*.json")
        ]
        assert len(expected_sdist_schemas) > 0

        missing_sdist = [s for s in expected_sdist_schemas if s not in sdist_members]
        assert not missing_sdist, f"Schemas missing from sdist: {missing_sdist}"

        # 3. Verify the wheel package (.whl)
        wheels = list(dist_dir.glob("*.whl"))
        assert len(wheels) == 1, f"Expected 1 wheel, but found {len(wheels)}."
        wheel_path = wheels[0]
        with zipfile.ZipFile(wheel_path, "r") as zf:
            wheel_members = zf.namelist()

        # In wheels, data files are often in a different location
        expected_wheel_schemas = [
            f"llm_common/contracts/schemas/{p.name}"
            for p in (repo_root / "llm_common" / "contracts" / "schemas").glob("*.json")
        ]
        assert len(expected_wheel_schemas) > 0

        missing_wheel = [s for s in expected_wheel_schemas if s not in wheel_members]
        assert not missing_wheel, f"Schemas missing from wheel: {missing_wheel}"

    finally:
        # 4. Clean up the dist directory
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
