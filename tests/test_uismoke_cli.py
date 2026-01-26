import sys
from unittest.mock import MagicMock, patch

import pytest
from llm_common.agents.uismoke_runner import main

def test_cli_exit_qa_mode_with_failures():
    """QA mode should exit 0 even if there are failures, provided the runner completes."""
    with patch("argparse.ArgumentParser.parse_args") as mock_args, \
         patch("llm_common.agents.uismoke_runner.UISmokeRunner") as MockRunner:
        
        mock_args.return_value = MagicMock(
            command="run",
            stories="stories",
            base_url="http://localhost",
            output="out",
            mode="qa",
            auth_mode="none",
            # Add other required args with defaults
            repro=1, headless=True, tracing=False,
            suite_timeout=5400, story_timeout=900,
            max_tool_iterations=12, nav_timeout_ms=30000,
            action_timeout_ms=30000, block_domains=None,
            no_default_blocklist=False, only_stories=None,
            cookie_name=None, cookie_value=None,
            cookie_domain=None, cookie_signed=False,
            cookie_secret_env=None, email=None,
            password=None, email_env=None,
            password_env=None, storage_state=None
        )
        
        runner_instance = MockRunner.return_value
        
        # Make runner.run return a coroutine that returns False
        async def mock_run():
            return False
        runner_instance.run.side_effect = mock_run
        
        runner_instance.completed_ok = True      # Harness finished fine
        
        # We expect sys.exit(0)
        with pytest.raises(SystemExit) as cm:
            main()
        assert cm.value.code == 0

def test_cli_exit_gate_mode_with_failures():
    """Gate mode should exit 1 if there are failures."""
    with patch("argparse.ArgumentParser.parse_args") as mock_args, \
         patch("llm_common.agents.uismoke_runner.UISmokeRunner") as MockRunner:
        
        mock_args.return_value = MagicMock(
            command="run",
            stories="stories",
            base_url="http://localhost",
            output="out",
            mode="gate",
            auth_mode="none",
             # Add other required args with defaults
            repro=1, headless=True, tracing=False,
            suite_timeout=5400, story_timeout=900,
            max_tool_iterations=12, nav_timeout_ms=30000,
            action_timeout_ms=30000, block_domains=None,
            no_default_blocklist=False, only_stories=None,
            cookie_name=None, cookie_value=None,
            cookie_domain=None, cookie_signed=False,
            cookie_secret_env=None, email=None,
            password=None, email_env=None,
            password_env=None, storage_state=None
        )
        
        runner_instance = MockRunner.return_value
        
        async def mock_run():
            return False
        runner_instance.run.side_effect = mock_run
        
        runner_instance.completed_ok = True
        
        # We expect sys.exit(1)
        with pytest.raises(SystemExit) as cm:
            main()
        assert cm.value.code == 1

def test_cli_exit_harness_crash():
    """QA mode should exit 1 if harness crashes (completed_ok = False)."""
    with patch("argparse.ArgumentParser.parse_args") as mock_args, \
         patch("llm_common.agents.uismoke_runner.UISmokeRunner") as MockRunner:
        
        mock_args.return_value = MagicMock(
            command="run",
            stories="stories",
            base_url="http://localhost",
            output="out",
            mode="qa",
            auth_mode="none",
             # Add other required args with defaults
            repro=1, headless=True, tracing=False,
            suite_timeout=5400, story_timeout=900,
            max_tool_iterations=12, nav_timeout_ms=30000,
            action_timeout_ms=30000, block_domains=None,
            no_default_blocklist=False, only_stories=None,
            cookie_name=None, cookie_value=None,
            cookie_domain=None, cookie_signed=False,
            cookie_secret_env=None, email=None,
            password=None, email_env=None,
            password_env=None, storage_state=None
        )
        
        runner_instance = MockRunner.return_value
        
        async def mock_run():
            return False
        runner_instance.run.side_effect = mock_run
        
        runner_instance.completed_ok = False # Harness crashed
        
        # We expect sys.exit(1)
        with pytest.raises(SystemExit) as cm:
            main()
        assert cm.value.code == 1
