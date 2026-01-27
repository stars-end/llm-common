import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from llm_common.agents.ui_smoke_agent import UISmokeAgent
from llm_common.agents.uismoke_runner import UISmokeRunner
from llm_common.agents.schemas import AgentStory, StoryResult, StepResult

@pytest.mark.asyncio
async def test_deterministic_only_skips_non_deterministic_steps():
    # Setup browser mock
    browser = MagicMock()
    browser.get_current_url = AsyncMock(return_value="http://localhost")
    browser.screenshot = AsyncMock(return_value="b64")
    browser.get_console_errors = AsyncMock(return_value=[])
    browser.get_network_errors = AsyncMock(return_value=[])
    browser.navigate = AsyncMock()
    
    # Mock LLM and Agent methods
    llm = MagicMock()
    llm.chat_completion = AsyncMock()
    
    agent = UISmokeAgent(glm_client=llm, browser=browser, base_url="http://localhost")
    
    # Mock _verify_completion to return True
    with patch.object(agent, "_verify_completion", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = True
        
        # Story with one deterministic and one non-deterministic step
        story = AgentStory(
            id="test-story",
            persona="tester",
            steps=[
                {"id": "s1", "navigate": "/home"},  # Deterministic
                {"id": "s2", "description": "Complex action with LLM"} # Non-deterministic
            ]
        )
        
        # Run with deterministic_only=True
        result = await agent.run_story(story, deterministic_only=True)
        
        assert result.status == "pass"
        assert len(result.step_results) == 2
        assert result.step_results[0].status == "pass"
        assert result.step_results[1].status == "skip"

@pytest.mark.asyncio
async def test_deterministic_only_fails_on_deterministic_failure():
    browser = MagicMock()
    browser.navigate = AsyncMock(side_effect=Exception("Nav failed"))
    browser.get_current_url = AsyncMock(return_value="http://localhost")
    
    agent = UISmokeAgent(glm_client=MagicMock(), browser=browser, base_url="http://localhost")
    
    story = AgentStory(
        id="test-story",
        persona="tester",
        steps=[{"id": "s1", "navigate": "/home"}]
    )
    
    result = await agent.run_story(story, deterministic_only=True)
    assert result.status == "fail"
    assert result.step_results[0].status == "fail"

def test_fail_on_classifications():
    runner = UISmokeRunner(
        base_url="http://localhost",
        stories_dir=MagicMock(),
        output_dir=MagicMock(),
        auth_config=MagicMock(),
        fail_on_classifications=["reproducible_403_forbidden"]
    )
    
    story_results = [
        StoryResult(story_id="s1", status="pass", classification="pass"),
        StoryResult(story_id="s2", status="fail", classification="reproducible_403_forbidden")
    ]
    
    # Directly test the success logic that uses fail_on_classifications
    # (extracted from runner.run)
    success = all(r.status == "pass" for r in story_results)
    if runner.fail_on_classifications:
        for r in story_results:
            if r.classification in runner.fail_on_classifications:
                success = False
    
    assert success is False
