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
            execution_mode=None,
            auth_mode="none",
            bootstrap=None,
            auth_redirect_check_path=None,
            # Add other required args with defaults
            repro=1, headless=True, tracing=False,
            suite_timeout=5400, story_timeout=900,
            max_tool_iterations=12, nav_timeout_ms=30000,
            action_timeout_ms=30000, block_domains=None,
            no_default_blocklist=False, only_stories=None,
            exclude_stories=None, deterministic_only=False,
            cookie_name=None, cookie_value=None,
            cookie_domain=None, cookie_signed=False,
            cookie_secret_env=None, email=None,
            password=None, email_env=None,
            password_env=None, storage_state=None,
            fail_on_classifications=None,
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
            execution_mode=None,
            auth_mode="none",
            bootstrap=None,
            auth_redirect_check_path=None,
             # Add other required args with defaults
            repro=1, headless=True, tracing=False,
            suite_timeout=5400, story_timeout=900,
            max_tool_iterations=12, nav_timeout_ms=30000,
            action_timeout_ms=30000, block_domains=None,
            no_default_blocklist=False, only_stories=None,
            exclude_stories=None, deterministic_only=False,
            cookie_name=None, cookie_value=None,
            cookie_domain=None, cookie_signed=False,
            cookie_secret_env=None, email=None,
            password=None, email_env=None,
            password_env=None, storage_state=None,
            fail_on_classifications=None,
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
            execution_mode=None,
            auth_mode="none",
            bootstrap=None,
            auth_redirect_check_path=None,
             # Add other required args with defaults
            repro=1, headless=True, tracing=False,
            suite_timeout=5400, story_timeout=900,
            max_tool_iterations=12, nav_timeout_ms=30000,
            action_timeout_ms=30000, block_domains=None,
            no_default_blocklist=False, only_stories=None,
            exclude_stories=None, deterministic_only=False,
            cookie_name=None, cookie_value=None,
            cookie_domain=None, cookie_signed=False,
            cookie_secret_env=None, email=None,
            password=None, email_env=None,
            password_env=None, storage_state=None,
            fail_on_classifications=None,
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


def test_cli_passes_generic_bootstrap_config_to_runner():
    """CLI should pass generic auth/bootstrap inputs without product labels."""
    with patch("argparse.ArgumentParser.parse_args") as mock_args, \
         patch("llm_common.agents.uismoke_runner.UISmokeRunner") as MockRunner:

        mock_args.return_value = MagicMock(
            command="run",
            stories="stories",
            base_url="http://localhost",
            output="out",
            mode="qa",
            execution_mode="deterministic",
            auth_mode="none",
            bootstrap="ui_login",
            auth_redirect_check_path="/v2",
            repro=1, headless=True, tracing=False,
            suite_timeout=5400, story_timeout=900,
            max_tool_iterations=12, nav_timeout_ms=30000,
            action_timeout_ms=30000, block_domains=None,
            no_default_blocklist=False, only_stories=None,
            cookie_name=None, cookie_value=None,
            cookie_domain=None, cookie_signed=False,
            cookie_secret_env=None, email=None,
            password=None, email_env=None,
            password_env=None, storage_state=None,
            exclude_stories=None, deterministic_only=False,
            fail_on_classifications=None,
        )

        runner_instance = MockRunner.return_value

        async def mock_run():
            return True

        runner_instance.run.side_effect = mock_run
        runner_instance.completed_ok = True
        runner_instance.report = MagicMock(story_results=[])

        with pytest.raises(SystemExit) as cm:
            main()

        assert cm.value.code == 0
        auth_config = MockRunner.call_args.kwargs["auth_config"]
        assert auth_config.mode == "none"
        assert auth_config.bootstrap == "ui_login"
        assert auth_config.auth_redirect_check_path == "/v2"
        assert MockRunner.call_args.kwargs["execution_mode"] == "deterministic"


def test_cli_rejects_conflicting_execution_flags():
    with patch("argparse.ArgumentParser.parse_args") as mock_args:
        mock_args.return_value = MagicMock(
            command="run",
            stories="stories",
            base_url="http://localhost",
            output="out",
            mode="qa",
            execution_mode="exploratory",
            auth_mode="none",
            bootstrap=None,
            auth_redirect_check_path=None,
            repro=1,
            headless=True,
            tracing=False,
            suite_timeout=5400,
            story_timeout=900,
            max_tool_iterations=12,
            nav_timeout_ms=30000,
            action_timeout_ms=30000,
            block_domains=None,
            no_default_blocklist=False,
            only_stories=None,
            exclude_stories=None,
            deterministic_only=True,
            cookie_name=None,
            cookie_value=None,
            cookie_domain=None,
            cookie_signed=False,
            cookie_secret_env=None,
            email=None,
            password=None,
            email_env=None,
            password_env=None,
            storage_state=None,
            fail_on_classifications=None,
        )

        with pytest.raises(SystemExit) as cm:
            main()
        assert cm.value.code == 2
