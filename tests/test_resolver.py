import os
import unittest
from unittest.mock import patch
from llm_common.environment.resolver import ServiceRegistry, RuntimeContext

class TestServiceRegistry(unittest.TestCase):
    def test_default_context(self):
        """Should default to LOCAL"""
        with patch.dict(os.environ, {}, clear=True):
            registry = ServiceRegistry()
            self.assertEqual(registry._context, RuntimeContext.LOCAL)
            self.assertEqual(registry.get_service_url("backend"), "http://localhost:8000")

    def test_railway_pr_detection(self):
        """Should detect Railway PR environment"""
        env = {
            "RAILWAY_ENVIRONMENT": "true",
            "RAILWAY_ENVIRONMENT_NAME": "pr-123"
        }
        with patch.dict(os.environ, env, clear=True):
            registry = ServiceRegistry()
            self.assertEqual(registry._context, RuntimeContext.RAILWAY_PR)
            # Should prefer explicit env var if set
            self.assertEqual(registry.get_service_url("backend"), "http://backend.railway.internal:8000")

    def test_explicit_env_var_override(self):
        """Env vars should override context logic"""
        env = {
            "BACKEND_URL": "https://api.production.com"
        }
        with patch.dict(os.environ, env, clear=True):
            registry = ServiceRegistry()
            self.assertEqual(registry.get_service_url("backend"), "https://api.production.com")

if __name__ == "__main__":
    unittest.main()
