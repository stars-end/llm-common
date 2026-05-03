from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from llm_common.persona_tester.deck import load_persona_deck
from llm_common.persona_tester.generator import generate_persona
from llm_common.persona_tester.manifest import (
    CompletionArtifacts,
    ManifestError,
    complete_run_manifest,
    init_run_manifest,
    update_generated_fields,
)
from llm_common.persona_tester.reporting import write_report_artifacts


def _load_deck_payload(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise ManifestError(f"YAML support unavailable: {exc}") from exc
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise ManifestError("Deck must be a mapping")
    return payload


def _deck_warnings_json(warnings: list[Any]) -> list[dict[str, str]]:
    return [
        {
            "rule_id": warning.rule_id,
            "severity": warning.severity,
            "message": warning.message,
        }
        for warning in warnings
    ]


def main() -> None:
    parser = argparse.ArgumentParser(prog="persona-tester")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate-deck")
    p_validate.add_argument("--deck", required=True)
    p_validate.add_argument("--product-key", required=True)

    p_generate = sub.add_parser("generate")
    p_generate.add_argument("--deck", required=True)
    p_generate.add_argument("--seed", required=True, type=int)
    p_generate.add_argument("--run-id", required=True)
    p_generate.add_argument("--manifest", required=True)
    p_generate.add_argument("--product-key", required=False)
    p_generate.add_argument("--scenario-count", type=int, default=1)

    p_init = sub.add_parser("init-run")
    p_init.add_argument("--deck", required=True)
    p_init.add_argument("--run-id", required=True)
    p_init.add_argument("--seed", required=True, type=int)
    p_init.add_argument("--manifest", required=True)
    p_init.add_argument("--environment", default="unknown")
    p_init.add_argument("--auth-user", default=None)

    p_complete = sub.add_parser("complete-run")
    p_complete.add_argument("--manifest", required=True)
    p_complete.add_argument("--status", required=True, choices=["completed", "failed"])
    p_complete.add_argument("--reports-dir", required=False)

    p_sum = sub.add_parser("summarize")
    p_sum.add_argument("--runs-dir", required=True)
    p_sum.add_argument("--product-key", required=False)

    args = parser.parse_args()
    try:
        if args.command == "validate-deck":
            result = load_persona_deck(args.deck, product_key=args.product_key)
            print(
                json.dumps(
                    {
                        "ok": True,
                        "deck_version": result.deck.deck_version,
                        "warnings": _deck_warnings_json(result.warnings),
                    }
                )
            )
            raise SystemExit(0)

        if args.command == "init-run":
            deck = _load_deck_payload(Path(args.deck))
            manifest = init_run_manifest(
                deck=deck,
                run_id=args.run_id,
                run_seed=args.seed,
                manifest_path=Path(args.manifest),
                environment=args.environment,
                auth_user=args.auth_user,
            )
            print(json.dumps({"ok": True, "manifest": manifest}))
            raise SystemExit(0)

        if args.command == "generate":
            result = load_persona_deck(args.deck, product_key=args.product_key)
            generated_persona = generate_persona(
                result.deck,
                seed=args.seed,
                persona_id=f"{args.run_id}-persona",
                display_name="Generated Persona",
                goals=[scenario.intent for scenario in result.deck.scenarios],
                constraints=result.deck.forbidden_actions,
                style={"tone": "neutral", "verbosity": "medium"},
                risk_tolerance="medium",
                skepticism_profile="medium",
                challenge_preferences=[
                    prompt
                    for scenario in result.deck.scenarios
                    for prompt in scenario.challenge_prompts
                ],
                refusal_preferences=[
                    probe for scenario in result.deck.scenarios for probe in scenario.refusal_probes
                ],
                product_extension={
                    "product_key": result.deck.product_key,
                    "deck_version": result.deck.deck_version,
                },
                scenario_count=args.scenario_count,
            )
            generated = {
                "persona_card": generated_persona.persona.model_dump(mode="json"),
                "persona_signature": generated_persona.signature,
                "scenario_cards": [
                    scenario.model_dump(mode="json") for scenario in generated_persona.scenarios
                ],
            }
            manifest = update_generated_fields(Path(args.manifest), generated_payload=generated)
            print(json.dumps({"ok": True, "manifest": manifest}))
            raise SystemExit(0)

        if args.command == "complete-run":
            manifest_path = Path(args.manifest)
            manifest = json.loads(manifest_path.read_text())
            artifacts = None
            if args.reports_dir:
                paths = write_report_artifacts(manifest=manifest, out_dir=Path(args.reports_dir))
                artifacts = CompletionArtifacts(report_paths=paths, summary_path=paths.get("summary_json"))
            completed = complete_run_manifest(manifest_path, status=args.status, artifacts=artifacts)
            print(json.dumps({"ok": True, "manifest": completed}))
            raise SystemExit(0)

        if args.command == "summarize":
            runs_dir = Path(args.runs_dir)
            manifests = sorted(runs_dir.glob("**/*.manifest.json"))
            rows = []
            for mpath in manifests:
                manifest = json.loads(mpath.read_text())
                if args.product_key and manifest.get("product_key") != args.product_key:
                    continue
                if manifest.get("status") not in ("completed", "failed"):
                    continue
                rows.append(
                    {
                        "run_id": manifest.get("run_id"),
                        "status": manifest.get("status"),
                        "product_key": manifest.get("product_key"),
                        "deck_version": manifest.get("deck_version"),
                        "summary_path": manifest.get("summary_path"),
                    }
                )
            print(json.dumps({"ok": True, "count": len(rows), "runs": rows}))
            raise SystemExit(0)

    except (ManifestError, FileNotFoundError, KeyError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
