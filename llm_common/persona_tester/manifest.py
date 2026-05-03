from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ManifestError(ValueError):
    pass


TERMINAL_STATUSES = {"completed", "failed"}
REQUIRED_GENERATION_FIELDS = ("persona_card", "persona_signature", "scenario_cards")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def create_initialized_manifest(
    *,
    run_id: str,
    run_seed: int,
    product_key: str,
    deck_version: str,
    environment: str | None = None,
    auth_user: str | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_seed": run_seed,
        "product_key": product_key,
        "deck_version": deck_version,
        "persona_card": None,
        "persona_signature": None,
        "scenario_cards": None,
        "environment": environment or "unknown",
        "auth_user": auth_user,
        "started_at": _now_iso(),
        "ended_at": None,
        "status": "initialized",
        "evidence_paths": [],
        "report_paths": {},
        "errors": [],
        "summary_path": None,
    }


def init_run_manifest(
    *,
    deck: dict[str, Any],
    run_id: str,
    run_seed: int,
    manifest_path: Path,
    environment: str | None = None,
    auth_user: str | None = None,
) -> dict[str, Any]:
    manifest = create_initialized_manifest(
        run_id=run_id,
        run_seed=run_seed,
        product_key=str(deck["product_key"]),
        deck_version=str(deck["deck_version"]),
        environment=environment,
        auth_user=auth_user,
    )
    _write_json(manifest_path, manifest)
    return manifest


def update_generated_fields(manifest_path: Path, *, generated_payload: dict[str, Any]) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    if manifest.get("status") in TERMINAL_STATUSES:
        raise ManifestError("Terminal manifest is immutable for generation updates")
    for field in REQUIRED_GENERATION_FIELDS:
        if field in generated_payload:
            manifest[field] = generated_payload[field]
    if all(manifest.get(field) is not None for field in REQUIRED_GENERATION_FIELDS):
        manifest["status"] = "generated"
    _write_json(manifest_path, manifest)
    return manifest


@dataclass(frozen=True)
class CompletionArtifacts:
    report_paths: dict[str, str] | None = None
    summary_path: str | None = None
    errors: list[dict[str, Any]] | None = None


def complete_run_manifest(
    manifest_path: Path,
    *,
    status: str,
    artifacts: CompletionArtifacts | None = None,
) -> dict[str, Any]:
    if status not in TERMINAL_STATUSES:
        raise ManifestError(f"Invalid terminal status: {status}")
    manifest = _load_json(manifest_path)
    existing_status = manifest.get("status")
    if existing_status in TERMINAL_STATUSES:
        if artifacts:
            if artifacts.report_paths is not None:
                manifest["report_paths"] = {**manifest.get("report_paths", {}), **artifacts.report_paths}
            if artifacts.summary_path is not None:
                manifest["summary_path"] = artifacts.summary_path
            if artifacts.errors:
                raise ManifestError("Terminal manifest is immutable except report/summary pointers")
            _write_json(manifest_path, manifest)
            return manifest
        raise ManifestError("Manifest already terminal")
    missing = [field for field in REQUIRED_GENERATION_FIELDS if manifest.get(field) is None]
    if missing:
        raise ManifestError(f"Cannot complete run; missing generation fields: {', '.join(missing)}")
    manifest["status"] = status
    manifest["ended_at"] = _now_iso()
    if artifacts:
        if artifacts.report_paths is not None:
            manifest["report_paths"] = {**manifest.get("report_paths", {}), **artifacts.report_paths}
        if artifacts.summary_path is not None:
            manifest["summary_path"] = artifacts.summary_path
        if artifacts.errors:
            manifest["errors"] = [*manifest.get("errors", []), *artifacts.errors]
    _write_json(manifest_path, manifest)
    return manifest
