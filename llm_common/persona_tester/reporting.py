from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class ReportPlugin(Protocol):
    def __call__(self, manifest: dict[str, Any]) -> dict[str, Any]:
        ...


def _md_list(items: list[str]) -> str:
    if not items:
        return "- (none)"
    return "\n".join(f"- {item}" for item in items)


def _emit_core_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    scenarios = manifest.get("scenario_cards") or []
    persona = manifest.get("persona_card") or {}
    return {
        "run_id": manifest.get("run_id"),
        "status": manifest.get("status"),
        "product_key": manifest.get("product_key"),
        "deck_version": manifest.get("deck_version"),
        "started_at": manifest.get("started_at"),
        "ended_at": manifest.get("ended_at"),
        "persona_id": persona.get("persona_id"),
        "persona_display_name": persona.get("display_name"),
        "scenario_ids": [s.get("scenario_id") for s in scenarios if isinstance(s, dict)],
        "novelty_notes": manifest.get("novelty_notes") or [],
        "errors": manifest.get("errors") or [],
    }


def render_report(
    manifest: dict[str, Any],
    *,
    plugin: ReportPlugin | None = None,
) -> tuple[str, dict[str, Any]]:
    summary = _emit_core_summary(manifest)
    plugin_sections: dict[str, Any] = {}
    plugin_error: str | None = None
    if plugin is not None:
        try:
            plugin_sections = plugin(manifest) or {}
        except Exception as exc:
            plugin_error = str(exc)
    if plugin_error:
        summary["plugin_error"] = plugin_error
    md = [
        "# Persona Tester Report",
        "",
        f"**Run ID**: `{summary['run_id']}`",
        f"**Status**: {summary['status']}",
        f"**Product**: `{summary['product_key']}`",
        f"**Deck Version**: `{summary['deck_version']}`",
        f"**Started**: {summary['started_at']}",
        f"**Ended**: {summary['ended_at']}",
        "",
        "## Persona",
        "",
        f"- ID: `{summary['persona_id']}`",
        f"- Name: {summary['persona_display_name']}",
        "",
        "## Scenarios",
        "",
        _md_list([str(sid) for sid in summary["scenario_ids"] if sid]),
        "",
        "## Novelty Notes",
        "",
        _md_list([str(note) for note in summary["novelty_notes"]]),
        "",
        "## Errors",
        "",
        _md_list([json.dumps(err, sort_keys=True) for err in summary["errors"]]),
    ]
    if plugin_sections:
        md.extend(["", "## Product Sections", "", "```json", json.dumps(plugin_sections, indent=2), "```"])
        summary["product_sections"] = plugin_sections
    if plugin_error:
        md.extend(["", "## Plugin Error", "", plugin_error])
    return "\n".join(md) + "\n", summary


def write_report_artifacts(
    *,
    manifest: dict[str, Any],
    out_dir: Path,
    plugin: ReportPlugin | None = None,
) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    markdown, summary = render_report(manifest, plugin=plugin)
    report_md = out_dir / "report.md"
    report_json = out_dir / "summary.json"
    report_md.write_text(markdown)
    report_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return {"report_md": str(report_md), "summary_json": str(report_json)}
