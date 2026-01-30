"""
Artifact Manager for Unified Verification Framework.

Handles screenshot naming, archiving, and artifact organization.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("verification.artifacts")


class ArtifactManager:
    """
    Manages verification artifacts (screenshots, logs, reports).

    Provides consistent naming, archiving, and cleanup.
    """

    def __init__(self, base_dir: str = "artifacts/verification"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_run_dir(self, run_id: str | None = None) -> Path:
        """Create directory for a verification run."""
        if run_id is None:
            run_id = f"verify-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        run_dir = self.base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "stories").mkdir(exist_ok=True)
        (run_dir / "logs").mkdir(exist_ok=True)

        logger.info(f"📁 Created run directory: {run_dir}")
        return run_dir

    def get_story_dir(self, run_dir: Path, story_id: str) -> Path:
        """Get the directory for a specific story's artifacts."""
        story_dir = run_dir / "stories" / story_id
        story_dir.mkdir(parents=True, exist_ok=True)
        return story_dir

    def get_attempt_dir(self, run_dir: Path, story_id: str, attempt: int) -> Path:
        """Get the directory for a specific attempt of a story."""
        attempt_dir = self.get_story_dir(run_dir, story_id) / "attempts" / str(attempt)
        attempt_dir.mkdir(parents=True, exist_ok=True)
        return attempt_dir

    def screenshot_path(self, run_dir: Path, story_id: str, attempt: int = 1, name: str = "final") -> Path:
        """Generate standardized screenshot path within an attempt."""
        return self.get_attempt_dir(run_dir, story_id, attempt) / f"{name}.png"

    def log_path(self, run_dir: Path, name: str = "full_run") -> Path:
        """Generate log file path."""
        return run_dir / "logs" / f"{name}.log"

    def archive_run(self, run_id: str, archive_dir: str | None = None) -> Path:
        """Archive a verification run to compressed format."""
        run_dir = self.base_dir / run_id
        if not run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {run_dir}")

        archive_base = Path(archive_dir) if archive_dir else self.base_dir / "archive"
        archive_base.mkdir(parents=True, exist_ok=True)

        archive_path = archive_base / f"{run_id}.tar.gz"
        shutil.make_archive(
            str(archive_path).replace(".tar.gz", ""), "gztar", run_dir.parent, run_dir.name
        )

        logger.info(f"📦 Archived: {archive_path}")
        return archive_path

    def cleanup_old_runs(self, keep_count: int = 10) -> int:
        """Remove old verification runs, keeping the most recent."""
        runs = sorted(
            [d for d in self.base_dir.iterdir() if d.is_dir() and d.name.startswith("verify-")],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )

        removed = 0
        for run_dir in runs[keep_count:]:
            shutil.rmtree(run_dir)
            removed += 1
            logger.info(f"🗑️ Removed old run: {run_dir.name}")

        return removed

    def get_latest_run(self) -> Path | None:
        """Get the most recent verification run directory."""
        runs = sorted(
            [d for d in self.base_dir.iterdir() if d.is_dir() and d.name.startswith("verify-")],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        return runs[0] if runs else None

    def list_runs(self) -> list[dict]:
        """List all verification runs with metadata."""
        runs = []
        for d in self.base_dir.iterdir():
            if d.is_dir() and d.name.startswith("verify-"):
                summary_file = d / "summary.json"
                runs.append(
                    {
                        "run_id": d.name,
                        "path": str(d),
                        "created": datetime.fromtimestamp(d.stat().st_mtime).isoformat(),
                        "has_summary": summary_file.exists(),
                    }
                )
        return sorted(runs, key=lambda r: r["created"], reverse=True)
