import json
import unittest

from llm_common.agents.provenance import Evidence, EvidenceEnvelope
from llm_common.agents.tools import ToolResult


class TestToolResult(unittest.TestCase):
    def test_tool_result_serialization(self):
        """Verify ToolResult serializes correctly to dict and JSON."""
        evidence = Evidence(
            kind="url",
            label="Example",
            url="http://example.com",
            content="Example content",
        )
        envelope = EvidenceEnvelope(evidence=[evidence], source_tool="test_tool")
        result = ToolResult(
            success=True,
            data={"foo": "bar"},
            source_urls=["http://example.com"],
            evidence=[envelope],
        )

        # Test dict serialization
        result_dict = result.model_dump()
        self.assertEqual(result_dict["schema_version"], 1.0)
        self.assertTrue(result_dict["success"])
        self.assertEqual(result_dict["data"], {"foo": "bar"})
        self.assertEqual(result_dict["source_urls"], ["http://example.com"])
        self.assertEqual(len(result_dict["evidence"]), 1)
        self.assertEqual(result_dict["evidence"][0]["source_tool"], "test_tool")

        # Test JSON serialization
        result_json = result.model_dump_json(indent=2)
        result_loaded = json.loads(result_json)
        self.assertEqual(result_loaded["schema_version"], 1.0)
        self.assertTrue(result_loaded["success"])


if __name__ == "__main__":
    unittest.main()
