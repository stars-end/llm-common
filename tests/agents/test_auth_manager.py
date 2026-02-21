import pytest
from unittest.mock import MagicMock, AsyncMock
import os
from llm_common.agents.auth import AuthConfig, AuthManager

@pytest.mark.asyncio
async def test_apply_auth_sets_bypass_key_header():
    # Setup config
    secret = "super-secret-key"
    config = AuthConfig(
        mode="cookie_bypass",
        cookie_name="x-test-user",
        cookie_value="test-user",
        cookie_secret_env="TEST_AUTH_BYPASS_SECRET"
    )
    
    # Mock environment
    os.environ["TEST_AUTH_BYPASS_SECRET"] = secret
    
    # Mock adapter/page/context
    mock_adapter = MagicMock()
    mock_adapter.base_url = "https://app.up.railway.app"
    mock_page = AsyncMock()
    mock_context = AsyncMock()
    mock_page.context = mock_context
    mock_adapter.page = mock_page
    
    manager = AuthManager(config)
    
    # Execute
    success = await manager.apply_auth(mock_adapter)
    
    # Assert
    assert success is True
    # Verify header was set
    mock_context.set_extra_http_headers.assert_called_once_with({"x-test-bypass-key": secret})
    # Verify cookie was added
    mock_context.add_cookies.assert_called_once()
