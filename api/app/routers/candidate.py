"""Everything a candidate can reach. No authentication beyond the token in
the URL; the token IS the credential."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Answer, Candidate, CandidateStatus, Question
from ..schemas import AnswerIn, AnswerPublic, CandidateView, QuestionPublic, SubmitPreview

router = APIRouter(prefix="/api/c", tags=["candidate"])


def _load(token: str, db: Session) -> Candidate:
    c = db.scalar(select(Candidate).where(Candidate.token == token))
    if c is None:
        # Same response as a well-formed but unknown token, so the endpoint
        # cannot be used to tell "never existed" from "revoked".
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such questionnaire")
    return c


def _is_answered(a: Answer | None, q: Question) -> bool:
    if a is None:
        return False
    if q.type.value == "mc":
        return bool(a.choices)
    return a.value is not None and a.value.strip() != ""


@router.get("/{token}", response_model=CandidateView)
def view(token: str, db: Session = Depends(get_db)) -> CandidateView:
    c = _load(token, db)
    if c.status == CandidateStatus.not_started:
        c.status = CandidateStatus.in_progress
        c.first_seen_at = datetime.now()
        db.commit()

    questions = list(db.scalars(select(Question).order_by(Question.position)))
    answers = {a.question_id: a for a in c.answers}

    return CandidateView(
        name=c.name,
        status=c.status.value,
        submitted_at=c.submitted_at,
        read_only=c.status == CandidateStatus.submitted,
        questions=[QuestionPublic.model_validate(q) for q in questions],
        answers={
            qid: AnswerPublic(question_id=qid, value=a.value, choices=a.choices,
                              comment=a.comment, updated_at=a.updated_at)
            for qid, a in answers.items()
        },
        answered=sum(1 for q in questions if _is_answered(answers.get(q.id), q)),
        total=len(questions),
    )


@router.put("/{token}/answers/{question_id}", response_model=AnswerPublic)
def save_answer(token: str, question_id: str, payload: AnswerIn,
                db: Session = Depends(get_db)) -> AnswerPublic:
    c = _load(token, db)
    if c.status == CandidateStatus.submitted:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "this questionnaire has been submitted and can no longer be changed")

    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such question")

    if payload.choices:
        valid = set(q.options or [])
        unknown = [ch for ch in payload.choices if ch not in valid]
        if unknown:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"not an option: {unknown}")
        if not q.multi_select and len(payload.choices) > 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "only one option may be chosen")

    a = db.scalar(select(Answer).where(Answer.candidate_id == c.id,
                                       Answer.question_id == question_id))
    if a is None:
        a = Answer(candidate_id=c.id, question_id=question_id)
        db.add(a)
    a.value = payload.value
    a.choices = payload.choices
    a.comment = payload.comment
    db.commit()
    db.refresh(a)
    return AnswerPublic(question_id=a.question_id, value=a.value, choices=a.choices,
                        comment=a.comment, updated_at=a.updated_at)


@router.get("/{token}/submit", response_model=SubmitPreview)
def submit_preview(token: str, db: Session = Depends(get_db)) -> SubmitPreview:
    """What is still blank, so the warning names it instead of being abstract."""
    c = _load(token, db)
    questions = list(db.scalars(select(Question).order_by(Question.position)))
    answers = {a.question_id: a for a in c.answers}
    unanswered = [q.num for q in questions if not _is_answered(answers.get(q.id), q)]
    return SubmitPreview(
        total=len(questions),
        answered=len(questions) - len(unanswered),
        unanswered=unanswered,
        already_submitted=c.status == CandidateStatus.submitted,
    )


@router.post("/{token}/submit", response_model=CandidateView)
def submit(token: str, db: Session = Depends(get_db)) -> CandidateView:
    c = _load(token, db)
    if c.status == CandidateStatus.submitted:
        raise HTTPException(status.HTTP_409_CONFLICT, "already submitted")
    c.status = CandidateStatus.submitted
    c.submitted_at = datetime.now()
    db.commit()
    return view(token, db)
