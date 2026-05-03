from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

AllowedOp = Literal["eq", "neq", "in", "not_in", "exists", "not_exists"]


class PersonaAnchor(BaseModel):
    key: str
    weight: int = Field(..., gt=0)


class PersonaCardBase(BaseModel):
    persona_id: str
    display_name: str
    anchors: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    style: dict[str, Any] = Field(default_factory=dict)
    risk_tolerance: str
    skepticism_profile: str
    challenge_preferences: list[str] = Field(default_factory=list)
    refusal_preferences: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    product_extension: dict[str, Any] = Field(default_factory=dict)
    product_extension_schema_version: str | None = None


class ScenarioCard(BaseModel):
    scenario_id: str
    title: str
    intent: str
    weight: int = Field(..., gt=0)
    challenge_prompts: list[str] = Field(default_factory=list)
    refusal_probes: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RulePredicate(BaseModel):
    path: str
    op: AllowedOp
    value: Any = None


class ContradictionRule(BaseModel):
    id: str
    severity: Literal["error", "warn"] = "error"
    all: list[RuleExpr] | None = None
    any: list[RuleExpr] | None = None
    not_: RuleExpr | None = Field(default=None, alias="not")

    @model_validator(mode="after")
    def validate_shape(self) -> ContradictionRule:
        set_count = int(self.all is not None) + int(self.any is not None) + int(self.not_ is not None)
        if set_count != 1:
            raise ValueError("ContradictionRule must contain exactly one of: all, any, not")
        if self.all is not None and len(self.all) == 0:
            raise ValueError("ContradictionRule all must be non-empty")
        if self.any is not None and len(self.any) == 0:
            raise ValueError("ContradictionRule any must be non-empty")
        return self

    model_config = {"populate_by_name": True}


RuleExpr = RulePredicate | ContradictionRule


class PersonaDeck(BaseModel):
    deck_version: str
    product_key: str
    product_extension_schema_version: str | None = None
    report_guidance: dict[str, Any] = Field(default_factory=dict)
    forbidden_actions: list[str] = Field(default_factory=list)
    contradiction_rules: list[ContradictionRule] = Field(default_factory=list)
    persona_anchors: list[PersonaAnchor]
    scenarios: list[ScenarioCard]

    @model_validator(mode="after")
    def validate_deck(self) -> PersonaDeck:
        if not self.deck_version.strip():
            raise ValueError("deck_version must be non-empty")
        if not self.product_key.strip():
            raise ValueError("product_key must be non-empty")
        if len(self.persona_anchors) == 0:
            raise ValueError("persona_anchors must be non-empty")
        if len(self.scenarios) == 0:
            raise ValueError("scenarios must be non-empty")
        scenario_ids = [s.scenario_id for s in self.scenarios]
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("scenario_id must be unique")
        return self
