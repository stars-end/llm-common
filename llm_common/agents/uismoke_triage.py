import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class UISmokeTriage:
    """Consumes run artifacts and generates Beads epics/subtasks."""

    def __init__(self, run_dir: Path, beads_epic_prefix: str, dry_run: bool = False):
        self.run_dir = run_dir
        self.beads_epic_prefix = beads_epic_prefix
        self.dry_run = dry_run

    def triage(self):
        """Perform triage and generate Beads plan."""
        run_json_path = self.run_dir / "run.json"
        if not run_json_path.exists():
            logger.error(f"run.json not found in {self.run_dir}")
            return

        with open(run_json_path) as f:
            run_data = json.load(f)

        repo = os.environ.get("GITHUB_REPOSITORY")
        if repo and "/" in repo:
            repo = repo.split("/")[-1]
        if not repo:
            # Prefer git root even if invoked from a subdir like `backend/`
            try:
                import subprocess

                root = subprocess.check_output(
                    ["git", "-C", str(self.run_dir), "rev-parse", "--show-toplevel"],
                    text=True,
                ).strip()
                repo = os.path.basename(root)
            except Exception:
                repo = os.path.basename(os.getcwd())
        env = run_data.get("environment", "unknown")
        date = datetime.now().strftime("%Y-%m-%d")
        epic_title = f"{self.beads_epic_prefix} UISmoke QA Run {repo} {env} {date}"

        stories_dir = self.run_dir / "stories"
        results = run_data.get("story_results", [])

        # Group by classification
        reproducible_fails = []
        flaky_issues = []
        capacity_issues = []

        for res in results:
            story_id = res.get("story_id")
            # Read story-level summary if available (for classification)
            summary_path = stories_dir / story_id / "story_summary.json"
            classification = "unknown"
            if summary_path.exists():
                with open(summary_path) as f:
                    summary_data = json.load(f)
                    classification = summary_data.get("classification", "unknown")
            else:
                # Fallback to result-level (single run)
                classification = res.get("classification") or "fail"

            if classification.startswith("reproducible_"):
                reproducible_fails.append((res, classification))
            elif classification == "flaky_inconclusive":
                flaky_issues.append(res)
            elif classification in ["suite_timeout", "timeout", "not_run"]:
                capacity_issues.append(res)

        if not reproducible_fails and not flaky_issues and not capacity_issues:
            logger.info("No failures to triage. Skipping Beads issue creation.")
            empty_plan = {
                "epic": {"title": epic_title, "description": "No issues detected."},
                "subtasks": [],
            }
            with open(self.run_dir / "beads_plan.json", "w") as f:
                json.dump(empty_plan, f, indent=2)
            if self.dry_run:
                print("\n=== BEADS TRIAGE PLAN (DRY RUN) ===")
                print("No issues detected.\n")
            return

        plan = {
            "epic": {
                "title": epic_title,
                "description": f"UISmoke QA failures from run {run_data.get('run_id')}.\nBase URL: {run_data.get('base_url')}",
            },
            "subtasks": [],
        }

        # 1 subtask per reproducible fail
        for res, classification in reproducible_fails:
            story_id = res.get("story_id")

            # Implementation for llm-uismoke-qa-loop.1: Hardened Triage
            summary_path = stories_dir / story_id / "story_summary.json"
            forensics_path = stories_dir / story_id / "forensics.json"

            last_url = "N/A"
            error_msgs = []
            deterministic_failure = False
            assertion_failure = False

            if forensics_path.exists():
                with open(forensics_path) as f:
                    forensics = json.load(f)
                    last_url = forensics.get("last_url", "N/A")
                    error_msgs = (forensics.get("console_errors") or []) + (
                        forensics.get("network_errors") or []
                    )
                    # classification in forensics might be different from summary? No, should match.

            if summary_path.exists():
                with open(summary_path) as f:
                    summary_data = json.load(f)
                    final_attempt = summary_data.get("final_attempt", {})

                    # Check if any failed step was deterministic
                    step_results = final_attempt.get("step_results", [])
                    for step in step_results:
                        if step.get("status") == "fail":
                            # Check actions_taken
                            actions = step.get("actions_taken", [])
                            if any(a.get("deterministic") for a in actions):
                                deterministic_failure = True

                            # Check errors for assertion-type
                            errors = step.get("errors", [])
                            for err in errors:
                                err_type = err.get("type")
                                err_msg = err.get("message", "").lower()
                                if (
                                    err_type in ["verification_error", "assert_text"]
                                    or "403_forbidden" in err_msg
                                ):
                                    assertion_failure = True

            # STRICT RULE: "Bug:" only if reproducible AND (deterministic OR assertion)
            is_bug = classification.startswith("reproducible_") and (
                deterministic_failure or assertion_failure
            )

            desc = f"Story: {story_id}\nClassification: {classification}\n"
            desc += f"Reason: {'Deterministic Step Failure' if deterministic_failure else 'Assertion Failure' if assertion_failure else 'Non-deterministic/Unknown'}\n"
            desc += f"Last URL: {last_url}\n"
            desc += "Errors:\n" + "\n".join(error_msgs[:5])
            desc += f"\n\nArtifacts: {stories_dir / story_id}"

            plan["subtasks"].append(
                {
                    "title": f"{'Bug' if is_bug else 'Triage'}: {story_id} ({classification})",
                    "description": desc,
                    "priority": 2 if is_bug else 3,
                }
            )

        # Aggregate flaky
        if flaky_issues:
            desc = "Stories that failed once but passed on rerun or had inconsistent errors:\n"
            desc += "\n".join([f"- {r.get('story_id')}" for r in flaky_issues])
            plan["subtasks"].append(
                {
                    "title": "Aggregate: Flaky/Inconclusive UI Stories",
                    "description": desc,
                    "priority": 3,
                }
            )

        # Aggregate capacity/config
        if capacity_issues:
            desc = "Stories that timed out or were not run due to suite limits:\n"
            desc += "\n".join([f"- {r.get('story_id')}" for r in capacity_issues])
            plan["subtasks"].append(
                {
                    "title": "Aggregate: Capacity/Timeout/Config Issues",
                    "description": desc,
                    "priority": 3,
                }
            )

        # Always write beads_plan.json into run dir for auditability
        with open(self.run_dir / "beads_plan.json", "w") as f:
            json.dump(plan, f, indent=2)
        logger.info(f"Beads plan written to {self.run_dir / 'beads_plan.json'}")

        if self.dry_run:
            print("\n=== BEADS TRIAGE PLAN (DRY RUN) ===")
            print(f"EPIC: {plan['epic']['title']}")
            for t in plan["subtasks"]:
                print(f"  [Task] {t['title']} (P{t['priority']})")
                print(f"         {t['description'].splitlines()[0]}...")
            print("===================================\n")
        else:
            self._execute_beads_plan(plan)

    def _execute_beads_plan(self, plan):
        """Execute plan via bd CLI."""
        import subprocess

        try:
            # Create Epic
            epic_cmd = [
                "bd",
                "create",
                "epic",
                plan["epic"]["title"],
                "--description",
                plan["epic"]["description"],
                "--priority",
                "1",
            ]
            proc = subprocess.run(epic_cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                logger.error(f"Failed to create Beads epic: {proc.stderr}")
                return

            # Extract epic ID from output (e.g. "✓ Created issue: llm-xxx")
            import re

            match = re.search(r"Created issue: ([a-zA-Z0-9-]+)", proc.stdout)
            if not match:
                logger.error(f"Could not parse epic ID from output: {proc.stdout}")
                return
            epic_id = match.group(1)
            logger.info(f"Created Beads epic: {epic_id}")

            for task in plan["subtasks"]:
                task_cmd = [
                    "bd",
                    "create",
                    "task",
                    task["title"],
                    "--parent",
                    epic_id,
                    "--description",
                    task["description"],
                    "--priority",
                    str(task["priority"]),
                ]
                subprocess.run(task_cmd)
                logger.info(f"Created subtask for {task['title']}")

        except FileNotFoundError:
            logger.warning("bd CLI not found. Writing beads_plan.json instead.")
            with open(self.run_dir / "beads_plan.json", "w") as f:
                json.dump(plan, f, indent=2)
            logger.info(f"Beads plan written to {self.run_dir / 'beads_plan.json'}")


def main():
    parser = argparse.ArgumentParser(description="UISmoke Triage Tool")
    parser.add_argument("--run-dir", required=True, help="Path to the UISmoke run directory")
    parser.add_argument(
        "--beads-epic-prefix", default="[UISmoke]", help="Prefix for the created Beads epic"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print plan instead of creating issues"
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    triager = UISmokeTriage(Path(args.run_dir), args.beads_epic_prefix, args.dry_run)
    triager.triage()


if __name__ == "__main__":
    main()
