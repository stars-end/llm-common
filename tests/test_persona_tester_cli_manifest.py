import json
from pathlib import Path

import pytest

from llm_common.persona_tester import manifest as manifest_mod
from llm_common.persona_tester.cli import main


def _write_deck(path: Path) -> None:
    path.write_text(
        """
deck_version: "2026-05-03.1"
product_key: "prime-radiant"
persona_anchors:
  - key: "methodical"
    weight: 1
scenarios:
  - scenario_id: "s1"
    title: "Scenario 1"
    intent: "Intent"
    weight: 1
""".strip()
        + "\n"
    )


def test_manifest_lifecycle_requires_generation_fields(tmp_path: Path) -> None:
    manifest_path = tmp_path / "run.manifest.json"
    deck = {"product_key": "prime-radiant", "deck_version": "2026-05-03.1"}
    manifest_mod.init_run_manifest(deck=deck, run_id="r1", run_seed=7, manifest_path=manifest_path)
    with pytest.raises(manifest_mod.ManifestError):
        manifest_mod.complete_run_manifest(manifest_path, status="completed")
    manifest_mod.update_generated_fields(
        manifest_path,
        generated_payload={
            "persona_card": {"persona_id": "p1", "display_name": "P1"},
            "persona_signature": "sig",
            "scenario_cards": [{"scenario_id": "s1"}],
        },
    )
    done = manifest_mod.complete_run_manifest(manifest_path, status="completed")
    assert done["status"] == "completed"
    assert done["ended_at"] is not None


def test_cli_validate_init_generate_complete_summarize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deck = tmp_path / "deck.yml"
    manifest = tmp_path / "r1.manifest.json"
    reports_dir = tmp_path / "reports"
    _write_deck(deck)

    monkeypatch.setattr("sys.argv", ["persona-tester", "validate-deck", "--deck", str(deck), "--product-key", "prime-radiant"])
    with pytest.raises(SystemExit) as ex:
        main()
    assert ex.value.code == 0

    monkeypatch.setattr("sys.argv", ["persona-tester", "init-run", "--deck", str(deck), "--run-id", "r1", "--seed", "42", "--manifest", str(manifest)])
    with pytest.raises(SystemExit) as ex:
        main()
    assert ex.value.code == 0

    monkeypatch.setattr("sys.argv", ["persona-tester", "generate", "--deck", str(deck), "--seed", "42", "--run-id", "r1", "--manifest", str(manifest)])
    with pytest.raises(SystemExit) as ex:
        main()
    assert ex.value.code == 0

    monkeypatch.setattr("sys.argv", ["persona-tester", "complete-run", "--manifest", str(manifest), "--status", "completed", "--reports-dir", str(reports_dir)])
    with pytest.raises(SystemExit) as ex:
        main()
    assert ex.value.code == 0
    payload = json.loads(manifest.read_text())
    assert payload["status"] == "completed"
    assert payload["ended_at"] is not None
    assert "report_md" in payload["report_paths"]
    summary = json.loads((reports_dir / "summary.json").read_text())
    assert summary["status"] == "completed"
    assert summary["ended_at"] is not None
    report = (reports_dir / "report.md").read_text()
    assert "**Status**: completed" in report
    assert "**Ended**: None" not in report

    monkeypatch.setattr("sys.argv", ["persona-tester", "summarize", "--runs-dir", str(tmp_path), "--product-key", "prime-radiant"])
    with pytest.raises(SystemExit) as ex:
        main()
    assert ex.value.code == 0
