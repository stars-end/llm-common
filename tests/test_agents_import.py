import subprocess
import sys
from pathlib import Path


def test_agents_import_without_playwright():
    """Prove that importing llm_common.agents doesn't require playwright."""
    # We use a subprocess to ensure a clean state
    # We mock out playwright by adding a dummy 'playwright' module to sys.modules that raises ImportError if accessed

    # Get the project root to ensure llm_common is in path
    project_root = Path(__file__).parents[2]

    code = f"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(r'{project_root}')))

# Mock missing playwright
sys.modules['playwright'] = None
sys.modules['playwright.async_api'] = None

try:
    import llm_common.agents
    print("SUCCESS")
except ImportError as e:
    print(f"FAILURE: {{e}}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {{e}}")
    sys.exit(1)
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
    assert result.returncode == 0
    assert "SUCCESS" in result.stdout
