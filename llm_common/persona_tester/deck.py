from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from llm_common.persona_tester.schemas import PersonaDeck


@dataclass
class DeckValidationMessage:
    rule_id: str
    severity: str
    message: str


@dataclass
class DeckValidationResult:
    deck: PersonaDeck
    warnings: list[DeckValidationMessage]


def _lookup_path(snapshot: dict[str, Any], dotted_path: str) -> tuple[bool, Any]:
    current: Any = snapshot
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return (False, None)
        current = current[part]
    return (True, current)


def _predicate_true(snapshot: dict[str, Any], predicate: dict[str, Any]) -> tuple[bool, bool]:
    exists, value = _lookup_path(snapshot, predicate["path"])
    op = predicate["op"]
    target = predicate.get("value")

    if op == "exists":
        return (True, exists)
    if op == "not_exists":
        return (True, not exists)
    if not exists:
        return (False, False)
    if op == "eq":
        return (True, value == target)
    if op == "neq":
        return (True, value != target)
    if op == "in":
        return (True, value in target)
    if op == "not_in":
        return (True, value not in target)
    return (True, False)


def _expr_true(snapshot: dict[str, Any], expr: dict[str, Any]) -> tuple[bool, bool]:
    if "path" in expr:
        return _predicate_true(snapshot, expr)
    if "all" in expr:
        known = True
        out = True
        for child in expr["all"]:
            child_known, child_out = _expr_true(snapshot, child)
            known = known and child_known
            out = out and child_out
        return (known, out)
    if "any" in expr:
        known = True
        out = False
        for child in expr["any"]:
            child_known, child_out = _expr_true(snapshot, child)
            known = known and child_known
            out = out or child_out
        return (known, out)
    if "not" in expr:
        child_known, child_out = _expr_true(snapshot, expr["not"])
        return (child_known, not child_out)
    return (True, False)


def load_persona_deck(path: str, product_key: str | None = None) -> DeckValidationResult:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    deck = PersonaDeck.model_validate(raw)
    if product_key is not None and deck.product_key != product_key:
        raise ValueError(f"product_key mismatch: expected {product_key}, got {deck.product_key}")

    warnings: list[DeckValidationMessage] = []
    deck_snapshot = deck.model_dump(by_alias=True)
    for rule in deck.contradiction_rules:
        known, matched = _expr_true(deck_snapshot, rule.model_dump(by_alias=True, exclude_none=True))
        if matched and rule.severity == "error":
            raise ValueError(f"blocking contradiction rule triggered: {rule.id}")
        if (not known) or matched:
            if rule.severity == "warn":
                warnings.append(
                    DeckValidationMessage(
                        rule_id=rule.id,
                        severity="warn",
                        message="contradiction rule warning" if matched else "unknown path in warn rule",
                    )
                )
            elif not known:
                raise ValueError(f"unknown path in error rule: {rule.id}")
    return DeckValidationResult(deck=deck, warnings=warnings)
