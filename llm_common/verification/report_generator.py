"""
Report Generator for Unified Verification Framework.

Generates Markdown reports with embedded screenshots and JSON summaries.
"""

import json
import logging
from pathlib import Path

from .framework import StoryCategory, StoryStatus, VerificationReport

logger = logging.getLogger("verification.report")


class ReportGenerator:
    """
    Generates verification reports in Markdown and JSON formats.

    Reports include:
    - Summary table (total/passed/failed/LLM calls)
    - Per-category breakdown
    - Each story with screenshot and GLM response
    """

    def __init__(self, report: VerificationReport):
        self.report = report

    def generate_markdown(self, output_path: Path | None = None) -> str:
        """Generate Markdown report with embedded screenshots."""
        r = self.report

        lines = [
            "# Verification Report",
            "",
            f"**Run ID**: `{r.config.run_id}`",
            f"**Started**: {r.start_time}",
            f"**Completed**: {r.end_time}",
            f"**Base URL**: {r.config.base_url or 'N/A'}",
            "",
            "---",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Stories | {r.total} |",
            f"| Passed | {r.passed} |",
            f"| Failed | {r.failed} |",
            f"| Skipped | {r.skipped} |",
            f"| Success Rate | {r.success_rate:.1f}% |",
            f"| LLM Calls | {r.total_llm_calls} |",
            "",
        ]

        # RAG Pipeline section
        rag_results = r.by_category(StoryCategory.RAG_PIPELINE)
        if rag_results:
            lines.extend(self._category_section("Affordabot RAG Pipeline", rag_results))

        # User Stories section
        user_results = r.by_category(StoryCategory.USER_STORY)
        if user_results:
            lines.extend(self._category_section("Prime-Radiant User Stories", user_results))

        # Integration section
        int_results = r.by_category(StoryCategory.INTEGRATION)
        if int_results:
            lines.extend(self._category_section("Integration Tests", int_results))

        content = "\n".join(lines)

        if output_path:
            output_path.write_text(content)
            logger.info(f"📄 Report saved: {output_path}")

        return content

    def _category_section(self, title: str, results: list) -> list:
        """Generate section for a category."""
        lines = [
            "---",
            "",
            f"## {title}",
            "",
        ]

        for result in results:
            status_emoji = {
                StoryStatus.PASSED: "✅",
                StoryStatus.FAILED: "❌",
                StoryStatus.SKIPPED: "⏭️",
                StoryStatus.PENDING: "⏳",
                StoryStatus.RUNNING: "🔄",
            }.get(result.status, "❓")

            lines.extend(
                [
                    f"### {result.story.id} {status_emoji}",
                    "",
                    f"**{result.story.name}**",
                    "",
                    f"- Status: {result.status.value}",
                    f"- Duration: {result.duration_seconds:.2f}s",
                    f"- LLM Calls: {result.llm_calls}",
                ]
            )

            if result.error:
                lines.extend(
                    [
                        f"- Error: `{result.error}`",
                    ]
                )

            if result.screenshot_path:
                # Use relative path for portability
                screenshot_name = Path(result.screenshot_path).name
                lines.extend(
                    [
                        "",
                        f"![{result.story.name}](screenshots/{screenshot_name})",
                    ]
                )

            if result.glm_response:
                lines.extend(
                    [
                        "",
                        "**GLM-4.6V Analysis**:",
                        "```",
                        result.glm_response[:500],  # Truncate long responses
                        "```",
                    ]
                )

            lines.append("")

        return lines

    def generate_json(self, output_path: Path | None = None) -> dict:
        """Generate JSON summary for machine consumption."""
        r = self.report

        summary = {
            "run_id": r.config.run_id,
            "start_time": r.start_time,
            "end_time": r.end_time,
            "base_url": r.config.base_url,
            "summary": {
                "total": r.total,
                "passed": r.passed,
                "failed": r.failed,
                "skipped": r.skipped,
                "success_rate": r.success_rate,
                "llm_calls": r.total_llm_calls,
            },
            "results": [
                {
                    "story_id": result.story.id,
                    "story_name": result.story.name,
                    "category": result.story.category.value,
                    "status": result.status.value,
                    "duration": result.duration_seconds,
                    "llm_calls": result.llm_calls,
                    "error": result.error,
                    "screenshot": result.screenshot_path,
                }
                for result in r.results
            ],
        }

        if output_path:
            output_path.write_text(json.dumps(summary, indent=2))
            logger.info(f"📄 JSON summary saved: {output_path}")

        return summary

    def save_all(self) -> tuple[Path, Path]:
        """Save both Markdown and JSON reports."""
        run_dir = self.report.config.run_dir

        md_path = run_dir / "report.md"
        json_path = run_dir / "summary.json"

        self.generate_markdown(md_path)
        self.generate_json(json_path)

        return md_path, json_path
