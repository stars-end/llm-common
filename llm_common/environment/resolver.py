import enum
import logging
import os

logger = logging.getLogger(__name__)


class RuntimeContext(enum.Enum):
    LOCAL = "local"
    RAILWAY_PR = "railway_pr"
    RAILWAY_DEV = "railway_dev"
    RAILWAY_PROD = "railway_prod"
    GITHUB_CI = "github_ci"
    JULES_SANDBOX = "jules_sandbox"


class ServiceRegistry:
    def __init__(self, overrides: dict[str, str] | None = None):
        self._overrides = overrides or {}
        self._context = self._detect_context()

    def _detect_context(self) -> RuntimeContext:
        if os.environ.get("DX_CONTEXT"):
            try:
                return RuntimeContext(os.environ["DX_CONTEXT"])
            except ValueError:
                pass
        if os.environ.get("RAILWAY_ENVIRONMENT"):
            env = os.environ.get("RAILWAY_ENVIRONMENT_NAME", "").lower()
            if "pr" in env or "pull" in env:
                return RuntimeContext.RAILWAY_PR
            if "production" in env:
                return RuntimeContext.RAILWAY_PROD
            return RuntimeContext.RAILWAY_DEV
        if os.environ.get("GITHUB_ACTIONS"):
            return RuntimeContext.GITHUB_CI
        return RuntimeContext.LOCAL

    def get_service_url(self, service_name: str, port: int = 8000) -> str:
        if service_name in self._overrides:
            return self._overrides[service_name]
        env_var = f"{service_name.upper()}_URL"
        if os.environ.get(env_var):
            return os.environ[env_var]
        if self._context == RuntimeContext.LOCAL:
            return f"http://localhost:{port}"
        if self._context == RuntimeContext.RAILWAY_PR:
            return f"http://{service_name}.railway.internal:{port}"
        return f"http://localhost:{port}"


resolver = ServiceRegistry()
