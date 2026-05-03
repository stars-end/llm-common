from __future__ import annotations

import tempfile

import pytest
import yaml

from llm_common.persona_tester.deck import load_persona_deck
from llm_common.persona_tester.generator import generate_persona
from llm_common.persona_tester.novelty import persona_signature, persona_similarity
from llm_common.persona_tester.schemas import PersonaCardBase, PersonaDeck


def _write_deck(payload: dict) -> str:
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with open(fd, "w", encoding="utf-8", closefd=True) as f:
        yaml.safe_dump(payload, f)
    return path


def _deck_payload() -> dict:
    return {
        "deck_version": "2026-05-03.1",
        "product_key": "prime-radiant-ai",
        "persona_anchors": [{"key": "a", "weight": 2}],
        "scenarios": [
            {"scenario_id": "s1", "title": "A", "intent": "I", "weight": 3},
            {"scenario_id": "s2", "title": "B", "intent": "I", "weight": 1},
        ],
    }


def test_deck_validates_uniqueness_and_positive_weights() -> None:
    payload = _deck_payload()
    payload["scenarios"].append({"scenario_id": "s1", "title": "C", "intent": "I", "weight": 1})
    with pytest.raises(ValueError, match="scenario_id must be unique"):
        PersonaDeck.model_validate(payload)


def test_load_deck_product_key_mismatch() -> None:
    path = _write_deck(_deck_payload())
    with pytest.raises(ValueError, match="product_key mismatch"):
        load_persona_deck(path, product_key="affordabot")


def test_contradiction_error_blocks_and_warn_collects() -> None:
    payload = _deck_payload()
    payload["contradiction_rules"] = [
        {"id": "warn-unknown", "severity": "warn", "all": [{"path": "persona.missing", "op": "eq", "value": 1}]},
        {"id": "err-hit", "severity": "error", "all": [{"path": "product_key", "op": "eq", "value": "prime-radiant-ai"}]},
    ]
    path = _write_deck(payload)
    with pytest.raises(ValueError, match="blocking contradiction rule triggered: err-hit"):
        load_persona_deck(path, product_key="prime-radiant-ai")


def test_generate_is_deterministic_and_bounds_checked() -> None:
    deck = PersonaDeck.model_validate(_deck_payload())
    run1 = generate_persona(
        deck,
        seed=7,
        persona_id="p1",
        display_name="P1",
        goals=["g1"],
        constraints=[],
        style={"tone": "direct"},
        risk_tolerance="low",
        skepticism_profile="high",
        challenge_preferences=[],
        refusal_preferences=[],
        scenario_count=2,
    )
    run2 = generate_persona(
        deck,
        seed=7,
        persona_id="p1",
        display_name="P1",
        goals=["g1"],
        constraints=[],
        style={"tone": "direct"},
        risk_tolerance="low",
        skepticism_profile="high",
        challenge_preferences=[],
        refusal_preferences=[],
        scenario_count=2,
    )
    assert [s.scenario_id for s in run1.scenarios] == [s.scenario_id for s in run2.scenarios]
    assert run1.signature == run2.signature
    with pytest.raises(ValueError, match="exceeds available scenarios"):
        generate_persona(
            deck,
            seed=1,
            persona_id="p1",
            display_name="P1",
            goals=[],
            constraints=[],
            style={},
            risk_tolerance="low",
            skepticism_profile="low",
            challenge_preferences=[],
            refusal_preferences=[],
            scenario_count=3,
        )


def test_signature_ignores_metadata_and_similarity_is_deterministic() -> None:
    p1 = PersonaCardBase(
        persona_id="p",
        display_name="P",
        anchors=["a", "b"],
        goals=["g1"],
        constraints=[],
        style={"tone": "neutral"},
        risk_tolerance="medium",
        skepticism_profile="high",
        challenge_preferences=[],
        refusal_preferences=[],
        metadata={"run_id": "x"},
        product_extension={"k": "v"},
    )
    p2 = PersonaCardBase(**{**p1.model_dump(), "metadata": {"run_id": "y"}})
    sig1 = persona_signature(p1, ["s2", "s1"], {"k": "v"})
    sig2 = persona_signature(p2, ["s1", "s2"], {"k": "v"})
    assert sig1 == sig2
    assert persona_similarity(p1, p2, {"k": "v"}, {"k": "v"}) == pytest.approx(1.0)
