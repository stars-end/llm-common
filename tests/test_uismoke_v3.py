
import pytest
import os
from unittest.mock import MagicMock, patch, AsyncMock
from llm_common.agents.uismoke_runner import UISmokeRunner
from llm_common.agents.ui_smoke_agent import UISmokeAgent
from llm_common.agents.schemas import StoryResult, AgentError, AgentStory

# --- A1: Classification Semantics ---

def test_classification_flaky_recovered():
    runner = UISmokeRunner(
        base_url="http://localhost",
        stories_dir=MagicMock(),
        output_dir=MagicMock(),
        auth_config=MagicMock(),
    )
    result1 = StoryResult(story_id="s1", status="fail", errors=[AgentError(type="timeout", severity="blocker", message="timeout")])
    result2 = StoryResult(story_id="s1", status="pass")
    
    classification = runner._get_final_classification([result1, result2])
    assert classification == "flaky_recovered"

def test_classification_pass():
    runner = UISmokeRunner(
        base_url="http://localhost",
        stories_dir=MagicMock(),
        output_dir=MagicMock(),
        auth_config=MagicMock(),
    )
    result1 = StoryResult(story_id="s1", status="pass")
    classification = runner._get_final_classification([result1])
    assert classification == "pass"

def test_classification_reproducible_failure():
    runner = UISmokeRunner(
        base_url="http://localhost",
        stories_dir=MagicMock(),
        output_dir=MagicMock(),
        auth_config=MagicMock(),
        repro_n=2
    )
    result1 = StoryResult(story_id="s1", status="fail", errors=[AgentError(type="timeout", severity="blocker", message="timeout")])
    result2 = StoryResult(story_id="s1", status="fail", errors=[AgentError(type="timeout", severity="blocker", message="timeout")])
    
    classification = runner._get_final_classification([result1, result2])
    assert classification == "reproducible_timeout"

def test_classification_flaky_inconclusive():
    runner = UISmokeRunner(
        base_url="http://localhost",
        stories_dir=MagicMock(),
        output_dir=MagicMock(),
        auth_config=MagicMock(),
        repro_n=2
    )
    result1 = StoryResult(story_id="s1", status="fail", errors=[AgentError(type="timeout", severity="blocker", message="timeout")])
    # Different error type in second attempt
    result2 = StoryResult(story_id="s1", status="fail", errors=[AgentError(type="network_error", severity="blocker", message="network")])
    
    classification = runner._get_final_classification([result1, result2])
    assert classification == "flaky_inconclusive"

def test_classification_single_failure():
    runner = UISmokeRunner(
        base_url="http://localhost",
        stories_dir=MagicMock(),
        output_dir=MagicMock(),
        auth_config=MagicMock(),
        repro_n=1
    )
    result1 = StoryResult(story_id="s1", status="fail", errors=[AgentError(type="timeout", severity="blocker", message="timeout")])
    
    classification = runner._get_final_classification([result1])
    assert classification == "single_timeout"

# --- A2: Exclude Stories ---

@pytest.mark.asyncio
async def test_exclude_stories_filtering():
    with patch("llm_common.agents.uismoke_runner.load_stories_from_directory") as mock_load:
        # Mock stories
        s1 = AgentStory(id="s1", persona="p1", steps=[])
        s2 = AgentStory(id="s2", persona="p1", steps=[])
        s3 = AgentStory(id="s3", persona="p1", steps=[])
        mock_load.return_value = [s1, s2, s3]
        
        runner = UISmokeRunner(
            base_url="http://localhost",
            stories_dir=MagicMock(),
            output_dir=MagicMock(),
            auth_config=MagicMock(),
            exclude_stories=["s2"]
        )
        
        # We can't easily mock the entire run loop without side effects, 
        # so we'll test the filtering logic directly if we extract it, 
        # or mock everything else.
        # Since logic is inside `run()`, let's just inspect how it handles list.
        # But `run()` calls `load_stories` then filters.
        
        # We will mock everything after the filtering
        with patch("os.environ.get", return_value="key"), \
             patch("llm_common.agents.uismoke_runner.GLMVisionClient") as MockGLM, \
             patch("llm_common.agents.uismoke_runner.AuthManager"), \
             patch.object(runner, "_run_story_with_repro") as mock_run_story, \
             patch.object(runner, "_write_artifacts"):
             
             # Ensure close() is awaitable
             MockGLM.return_value.close = AsyncMock()

             mock_run_story.return_value = {
                 "result": StoryResult(story_id="x", status="pass"), 
                 "authed_shared": None, "guest_shared": None
             }
             
             await runner.run()
             
             # Verify s2 was not run
             call_args = [args[0][0].id for args in mock_run_story.call_args_list]
             assert "s1" in call_args
             assert "s3" in call_args
             assert "s2" not in call_args

# --- A3: Deterministic Plaid / Env Substitution ---

@pytest.mark.asyncio
async def test_env_substitution_and_redaction():
    agent = UISmokeAgent(
        glm_client=MagicMock(),
        browser=MagicMock(),
        base_url="http://localhost"
    )
    
    with patch.dict(os.environ, {"PLAID_TEST_USER": "secret_user"}):
        # Substitution
        sub = agent._substitute_vars("Login with {{ENV:PLAID_TEST_USER}}")
        assert sub == "Login with secret_user"
        
        # Redaction
        red = agent._redact_secrets("Login with {{ENV:PLAID_TEST_USER}}")
        assert red == "Login with [REDACTED]"
        
        # Redaction of value (if we were to implement it, but we only redact the placeholder pattern currently in _redact_secrets)
        # The prompt says: "Ensure these actions substitute {{ENV:...}} only in deterministic paths, never in LLM prompts/logs"
        # The agent logic keeps placeholders in description for LLM prompts, but substitutes for deterministic actions.

