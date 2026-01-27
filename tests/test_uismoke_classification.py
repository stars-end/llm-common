
import pytest
from unittest.mock import MagicMock
from llm_common.agents.uismoke_runner import UISmokeRunner
from llm_common.agents.schemas import StoryResult, AgentError

def test_classification_status_timeout():
    runner = UISmokeRunner(
        base_url="http://localhost",
        stories_dir=MagicMock(),
        output_dir=MagicMock(),
        auth_config=MagicMock(),
    )
    # Even if error message doesn't say timeout, status=timeout should return "timeout"
    result = StoryResult(
        story_id="s1", 
        status="timeout", 
        errors=[AgentError(type="unknown", severity="blocker", message="Stopped due to limits")]
    )
    classification = runner._classify_failure(result)
    assert classification == "timeout"

def test_classification_status_not_run_suite_timeout():
    runner = UISmokeRunner(
        base_url="http://localhost",
        stories_dir=MagicMock(),
        output_dir=MagicMock(),
        auth_config=MagicMock(),
    )
    result = StoryResult(
        story_id="s1", 
        status="not_run", 
        errors=[AgentError(type="suite_timeout", severity="blocker", message="Suite timeout exceeded")]
    )
    classification = runner._classify_failure(result)
    assert classification == "suite_timeout"

def test_classification_status_not_run_auth_failed():
    runner = UISmokeRunner(
        base_url="http://localhost",
        stories_dir=MagicMock(),
        output_dir=MagicMock(),
        auth_config=MagicMock(),
    )
    result = StoryResult(
        story_id="s1", 
        status="not_run", 
        errors=[AgentError(type="auth_failed", severity="blocker", message="Auth verification failed")]
    )
    classification = runner._classify_failure(result)
    assert classification == "auth_failed"

def test_classification_status_not_run_generic():
    runner = UISmokeRunner(
        base_url="http://localhost",
        stories_dir=MagicMock(),
        output_dir=MagicMock(),
        auth_config=MagicMock(),
    )
    result = StoryResult(
        story_id="s1", 
        status="not_run", 
        errors=[AgentError(type="dependency", severity="blocker", message="Skipped due to dependency")]
    )
    classification = runner._classify_failure(result)
    # Should fall through to "not_run" if no specific error type matches
    assert classification == "not_run"

def test_classification_fallback_heuristics():
    runner = UISmokeRunner(
        base_url="http://localhost",
        stories_dir=MagicMock(),
        output_dir=MagicMock(),
        auth_config=MagicMock(),
    )
    # Fail status, check msg heuristics
    result = StoryResult(
        story_id="s1", 
        status="fail", 
        errors=[AgentError(type="error", severity="blocker", message="Some navigation failed here")]
    )
    classification = runner._classify_failure(result)
    assert classification == "navigation_failed"

    result_clerk = StoryResult(
        story_id="s2",
        status="fail",
        errors=[AgentError(type="error", severity="blocker", message="Clerk backend error")]
    )
    assert runner._classify_failure(result_clerk) == "clerk_failed"
