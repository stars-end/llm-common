from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from llm_common.persona_tester.novelty import persona_signature
from llm_common.persona_tester.schemas import PersonaCardBase, PersonaDeck, ScenarioCard


@dataclass
class GeneratedPersona:
    persona: PersonaCardBase
    scenarios: list[ScenarioCard]
    signature: str


def _sample_weighted(rng: random.Random, cards: list[ScenarioCard], count: int) -> list[ScenarioCard]:
    available = list(cards)
    selected: list[ScenarioCard] = []
    for _ in range(count):
        total = sum(card.weight for card in available)
        point = rng.uniform(0.0, float(total))
        acc = 0.0
        pick_index = 0
        for i, card in enumerate(available):
            acc += float(card.weight)
            if point <= acc:
                pick_index = i
                break
        selected.append(available.pop(pick_index))
    return selected


def generate_persona(
    deck: PersonaDeck,
    *,
    seed: int,
    persona_id: str,
    display_name: str,
    goals: list[str],
    constraints: list[str],
    style: dict[str, Any],
    risk_tolerance: str,
    skepticism_profile: str,
    challenge_preferences: list[str],
    refusal_preferences: list[str],
    product_extension: dict[str, Any] | None = None,
    scenario_count: int = 1,
) -> GeneratedPersona:
    if scenario_count > len(deck.scenarios):
        raise ValueError("requested scenario_count exceeds available scenarios")
    if scenario_count <= 0:
        raise ValueError("scenario_count must be positive")

    rng = random.Random(seed)
    selected = _sample_weighted(rng, deck.scenarios, scenario_count)
    persona = PersonaCardBase(
        persona_id=persona_id,
        display_name=display_name,
        anchors=[a.key for a in deck.persona_anchors],
        goals=goals,
        constraints=constraints,
        style=style,
        risk_tolerance=risk_tolerance,
        skepticism_profile=skepticism_profile,
        challenge_preferences=challenge_preferences,
        refusal_preferences=refusal_preferences,
        product_extension=product_extension or {},
    )
    signature = persona_signature(
        persona=persona,
        selected_scenario_ids=[s.scenario_id for s in selected],
        product_extension=persona.product_extension,
    )
    return GeneratedPersona(persona=persona, scenarios=selected, signature=signature)
