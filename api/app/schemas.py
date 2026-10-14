"""Response shapes.

The important one is QuestionPublic: it is the candidate-facing view and it
has no baseline field at all. That is deliberate - the baseline cannot leak
through an endpoint that has no way to carry it.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class QuestionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    num: str
    text: str
    type: str
    options: list[str] | None = None
    multi_select: bool = False
    comment_prompt: str | None = None
    references: list[str] | None = None


class AnswerIn(BaseModel):
    value: str | None = None            # None means skipped
    choices: list[str] | None = None
    comment: str | None = None


class AnswerPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: str
    value: str | None = None
    choices: list[str] | None = None
    comment: str | None = None
    updated_at: datetime | None = None


class CandidateView(BaseModel):
    name: str
    status: str
    submitted_at: datetime | None = None
    read_only: bool
    questions: list[QuestionPublic]
    answers: dict[str, AnswerPublic]
    answered: int
    total: int


class SubmitPreview(BaseModel):
    """What the candidate is shown before the point of no return."""
    total: int
    answered: int
    unanswered: list[str]               # question numbers, so they can go back
    already_submitted: bool
