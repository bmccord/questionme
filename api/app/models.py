"""The whole schema. Six tables; no migration framework.

Deliberate shapes worth knowing before changing anything:

* A skipped answer is a row whose `value` is NULL - distinct from a row whose
  value is "". "Declined to answer" and "answered with nothing" are different
  facts, and only the first should be excluded from the Claude comparison.

* `Question.baseline` is Nathan Tate's answer, stored verbatim. It is never
  shown to a candidate.

* `Prompt` rows are append-only. Editing the comparison prompt writes a new
  version; `Comparison.prompt_id` records which version produced a result, so
  two candidates analysed weeks apart stay comparable.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CandidateStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    submitted = "submitted"


class QuestionType(str, enum.Enum):
    text = "text"
    mc = "mc"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)          # "q13a"
    position: Mapped[int] = mapped_column(Integer, index=True)
    num: Mapped[str] = mapped_column(String(16))                            # "13a"
    source_num: Mapped[str] = mapped_column(String(16))                     # original paper number
    text: Mapped[str] = mapped_column(Text)
    type: Mapped[QuestionType] = mapped_column(Enum(QuestionType))

    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    multi_select: Mapped[bool] = mapped_column(Boolean, default=False)

    baseline: Mapped[str | None] = mapped_column(Text, nullable=True)       # free text
    baseline_choices: Mapped[list | None] = mapped_column(JSON, nullable=True)
    baseline_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    comment_prompt: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comment_baseline: Mapped[str | None] = mapped_column(Text, nullable=True)

    references: Mapped[list | None] = mapped_column(JSON, nullable=True)    # ["q12"]


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus), default=CandidateStatus.not_started
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    answers: Mapped[list[Answer]] = relationship(back_populates="candidate",
                                                 cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("candidate_id", "question_id", name="uq_answer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))

    # NULL means skipped. "" means they typed nothing and moved on - we keep
    # the distinction because the admin view and the comparison treat them
    # differently.
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    choices: Mapped[list | None] = mapped_column(JSON, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    candidate: Mapped[Candidate] = relationship(back_populates="answers")


class Prompt(Base):
    """Append-only. The comparison prompt is data, not code - it is edited in
    the admin console and never committed to this repository."""
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    body: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Comparison(Base):
    __tablename__ = "comparisons"
    # One row per answer COMPONENT, not per question: a multiple-choice
    # question has a selection and an optional comment, and they are judged
    # differently - the selection by set equality, the comment by Claude.
    __table_args__ = (UniqueConstraint("candidate_id", "question_id", "part",
                                       name="uq_comparison"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    part: Mapped[str] = mapped_column(String(16), default="answer")   # "answer" | "comment"
    prompt_id: Mapped[int | None] = mapped_column(ForeignKey("prompts.id"), nullable=True)

    # "match" | "partial" | "differs" | "not_answered"
    verdict: Mapped[str] = mapped_column(String(32), index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_deterministic: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
