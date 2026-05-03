from __future__ import annotations

import hashlib
import json
from typing import Any

from llm_common.persona_tester.schemas import PersonaCardBase


def persona_signature(
    persona: PersonaCardBase, selected_scenario_ids: list[str], product_extension: dict[str, Any]
) -> str:
    payload = {
        "persona": persona.model_dump(
            exclude={"metadata"},
            exclude_none=True,
            by_alias=True,
        ),
        "product_extension": product_extension,
        "selected_scenario_ids": sorted(selected_scenario_ids),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def persona_similarity(
    left: PersonaCardBase, right: PersonaCardBase, left_extension: dict[str, Any], right_extension: dict[str, Any]
) -> float:
    def jaccard(a: set[str], b: set[str]) -> float:
        if not a and not b:
            return 1.0
        union = a | b
        return len(a & b) / len(union) if union else 0.0

    score = 0.0
    score += 0.30 * jaccard(set(left.anchors), set(right.anchors))
    score += 0.25 * jaccard(set(left.goals), set(right.goals))
    score += 0.15 * (1.0 if left.style == right.style else 0.0)
    score += 0.15 * (1.0 if left.risk_tolerance == right.risk_tolerance else 0.0)
    score += 0.10 * (1.0 if left.skepticism_profile == right.skepticism_profile else 0.0)
    score += 0.05 * (1.0 if left_extension == right_extension else 0.0)
    return max(0.0, min(1.0, score))
