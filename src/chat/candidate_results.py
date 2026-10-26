"""Typed tool artifacts for chat cards. No parsing of model-written prose."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from src.candidates.service import visibility_conditions
from src.db import session as database
from src.db.models import Candidate


class Criterion(BaseModel):
    criterion: str = Field(max_length=500)
    score: float = Field(ge=1, le=5, allow_inf_nan=False)
    justification: str = Field(max_length=10000)


class EvaluationCard(BaseModel):
    candidate_id: UUID
    overall_score: float = Field(ge=1, le=5, allow_inf_nan=False)
    summary: str = Field(max_length=10000)
    criteria: list[Criterion] = Field(default_factory=list, max_length=30)
    strengths: list[str] = Field(default_factory=list, max_length=20)
    concerns: list[str] = Field(default_factory=list, max_length=20)


class Artifact(BaseModel):
    kind: Literal["candidate_ranking", "candidate_evaluation"]
    title: str = Field(max_length=500)
    items: list[EvaluationCard] = Field(max_length=10)


class VisibleCard(EvaluationCard):
    full_name: str
    applied_position: str | None
    rank: int


class ResultGroup(BaseModel):
    kind: Literal["candidate_ranking", "candidate_evaluation"]
    title: str
    items: list[VisibleCard]
    unavailable: bool = False


TOOL_KINDS = {"find_top_candidates_for_jd": "candidate_ranking",
              "evaluate_candidate_against_jd": "candidate_evaluation"}


def project_artifacts(artifacts):
    valid = []
    for tool_name, payload in artifacts:
        try:
            parsed = Artifact.model_validate(payload)
        except (ValidationError, TypeError):
            continue
        if TOOL_KINDS.get(tool_name) == parsed.kind:
            valid.append(parsed)
    if not valid:
        return []
    ids = {str(item.candidate_id) for group in valid for item in group.items}
    conditions = visibility_conditions()
    with database.SessionLocal() as db:
        rows = db.execute(select(Candidate.candidate_id, Candidate.full_name, Candidate.applied_position)
            .where(Candidate.candidate_id.in_(ids), *conditions)).all() if ids else []
    allowed = {row.candidate_id: row for row in rows}
    groups = []
    for group in valid:
        items, seen = [], set()
        for rank, item in enumerate(group.items, 1):
            cid = str(item.candidate_id)
            if cid not in allowed or cid in seen:
                continue
            seen.add(cid)
            row = allowed[cid]
            items.append({**item.model_dump(mode="json"), "rank": rank,
                          "full_name": row.full_name, "applied_position": row.applied_position})
        groups.append({"kind": group.kind, "title": group.title, "items": items,
                       "unavailable": any(str(i.candidate_id) not in allowed for i in group.items)})
    return groups
