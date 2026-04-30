from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class EvidenceStep(BaseModel):
    step_number: int
    action: str
    observation: str
    finding: str


class RootCauseAnalysis(BaseModel):
    incident_id: str
    root_cause_service: str
    root_cause_description: str
    evidence_chain: list[EvidenceStep] = Field(default_factory=list)
    contributing_factors: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    timeline: list[dict] = Field(default_factory=list)


class FixSuggestion(BaseModel):
    title: str
    description: str
    remediation_script: str | None = None
    confidence: float = 0.0
    risk_level: str = "medium"
    estimated_impact: str = ""
    prerequisites: list[str] = Field(default_factory=list)


class FixPlan(BaseModel):
    incident_id: str
    root_cause_id: str = ""
    suggestions: list[FixSuggestion] = Field(default_factory=list)
    recommended_action: str = ""


class PostIncidentReview(BaseModel):
    incident_id: str
    timeline_summary: str
    impact_assessment: str
    root_cause_summary: str
    what_went_well: list[str] = Field(default_factory=list)
    what_could_improve: list[str] = Field(default_factory=list)
    action_items: list[dict] = Field(default_factory=list)
    lessons_learned: str = ""
