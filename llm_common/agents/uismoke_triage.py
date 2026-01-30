import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

class UISmokeTriage:
    """Consumes run artifacts and generates Beads epics/subtasks."""

    def __init__(self, run_dir: Path, beads_epic_prefix: str = "Triage", dry_run: bool = False):
        self.run_dir = run_dir
        self.beads_epic_prefix = beads_epic_prefix
        self.dry_run = dry_run

    def triage(self) -> None:
        """Perform triage and generate beads_plan.json."""
        run_json_path = self.run_dir / "run.json"
        if not run_json_path.exists():
            logger.error(f"run.json not found in {self.run_dir}")
            return

        with open(run_json_path) as f:
            run_data = json.load(f)

        repo = os.environ.get("GITHUB_REPOSITORY", "").split("/")[-1] or os.path.basename(os.getcwd())
        env = run_data.get("environment", "unknown")
        date = datetime.now().strftime("%Y-%m-%d")
        epic_title = f"{self.beads_epic_prefix} UISmoke QA Run {repo} {env} {date}"

        results = run_data.get("story_results", [])

        bad_product = []  # Reproducible Failures (Assertions/Deterministic)
        bad_story = []    # Timeouts, Crashes, Prompt/Logic errors (Needs stability)
        bad_harness = []  # Auth, Navigation, Env issues (Harness Regressions)

        for res in results:
            classification = res.get("classification", "unknown")
            
            if classification.startswith("reproducible_"):
                bad_product.append(res)
            elif classification in ["timeout", "reproducible_timeout", "single_timeout"]:
                bad_story.append(res)
            elif classification in ["auth_failed", "clerk_failed", "navigation_failed"]:
                bad_harness.append(res)
            elif classification in ["flaky_recovered", "flaky_inconclusive"]:
                bad_story.append(res)
            else:
                bad_harness.append(res)

        plan = {
            "epic": {
                "title": epic_title,
                "description": f"UISmoke QA failures from run {run_data.get('run_id')}.\nBase URL: {run_data.get('base_url')}",
            },
            "subtasks": [],
        }

        if bad_product:
            desc = "Stories with Reproducible Failures (Target: BAD_PRODUCT):\n"
            desc += "\n".join([f"- {r.get('story_id')} ({r.get('classification')})" for r in bad_product])
            plan["subtasks"].append({
                "title": "Bug: Reproducible Product Regressions", 
                "description": desc, 
                "priority": 1
            })

        if bad_story:
            desc = "Stories that are unstable or timing out (Target: BAD_STORY):\n"
            desc += "\n".join([f"- {r.get('story_id')} ({r.get('classification')})" for r in bad_story])
            plan["subtasks"].append({
                "title": "Fix: UISmoke Story Stability / Optimization", 
                "description": desc, 
                "priority": 2
            })

        if bad_harness:
            desc = "Failures due to Harness or Environment issues (Target: BAD_HARNESS_OR_ENV):\n"
            desc += "\n".join([f"- {r.get('story_id')} ({r.get('classification')})" for r in bad_harness])
            plan["subtasks"].append({
                "title": "Investigate: Harness/Environment Regressions", 
                "description": desc, 
                "priority": 2
            })

        with open(self.run_dir / "beads_plan.json", "w") as f:
            json.dump(plan, f, indent=2)
            
        logger.info(f"Triage complete. Generated beads_plan.json in {self.run_dir}")

def main():
    parser = argparse.ArgumentParser(description="Triage UISmoke artifacts")
    parser.add_argument("--run-dir", required=True, type=Path, help="Path to run artifacts directory")
    parser.add_argument("--epic-prefix", default="Triage", help="Prefix for the Beads epic")
    parser.add_argument("--dry-run", action="store_true", help="Don't use bd CLI")
    
    args = parser.parse_args()
    
    triage_obj = UISmokeTriage(args.run_dir, beads_epic_prefix=args.epic_prefix, dry_run=args.dry_run)
    triage_obj.triage()

if __name__ == "__main__":
    main()
