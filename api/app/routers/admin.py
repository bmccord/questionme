"""The admin console API. One account, cookie session, everything behind
`require_admin` except the login itself."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import (Answer, Candidate, CandidateStatus, Comparison, Note, Prompt, Question)
from ..security import (SESSION_COOKIE, SESSION_MAX_AGE, check_admin, issue_session,
                        new_candidate_token, require_admin)
from ..services import comparison as comparison_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


class Login(BaseModel):
    username: str
    password: str


class NewCandidate(BaseModel):
    name: str
    email: str | None = None


class NoteIn(BaseModel):
    body: str


class PromptIn(BaseModel):
    body: str


@router.post("/login")
def login(payload: Login, request: Request, response: Response) -> dict:
    client = request.client.host if request.client else "unknown"
    if not check_admin(payload.username, payload.password, client):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong username or password")
    response.set_cookie(
        SESSION_COOKIE, issue_session(), max_age=SESSION_MAX_AGE,
        httponly=True, samesite="lax",
        secure=settings.environment not in ("local", "dev"),
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(user: str = Depends(require_admin)) -> dict:
    return {"user": user}


@router.get("/candidates")
def list_candidates(db: Session = Depends(get_db), _: str = Depends(require_admin)) -> list[dict]:
    questions = db.scalars(select(Question)).all()
    total = len(questions)
    qtype = {q.id: q.type.value for q in questions}
    out = []
    for c in db.scalars(select(Candidate).order_by(Candidate.created_at)):
        answered = sum(
            1 for a in c.answers
            if (a.choices if qtype.get(a.question_id) == "mc"
                else (a.value is not None and a.value.strip() != ""))
        )
        out.append({
            "id": c.id, "name": c.name, "email": c.email,
            "status": c.status.value, "answered": answered, "total": total,
            "created_at": c.created_at, "submitted_at": c.submitted_at,
            "link": f"{settings.public_base_url}/q/{c.token}",
        })
    return out


@router.post("/candidates", status_code=201)
def invite(payload: NewCandidate, db: Session = Depends(get_db),
           _: str = Depends(require_admin)) -> dict:
    c = Candidate(name=payload.name.strip(), email=(payload.email or "").strip() or None,
                  token=new_candidate_token())
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "name": c.name,
            "link": f"{settings.public_base_url}/q/{c.token}"}


@router.get("/candidates/{cid}")
def candidate_detail(cid: int, db: Session = Depends(get_db),
                     _: str = Depends(require_admin)) -> dict:
    c = db.get(Candidate, cid)
    if c is None:
        raise HTTPException(404, "no such candidate")
    questions = list(db.scalars(select(Question).order_by(Question.position)))
    answers = {a.question_id: a for a in c.answers}
    comps: dict[str, dict[str, Comparison]] = {}
    for comp in db.scalars(select(Comparison).where(Comparison.candidate_id == cid)):
        comps.setdefault(comp.question_id, {})[comp.part] = comp

    rows = []
    for q in questions:
        a = answers.get(q.id)
        parts = comps.get(q.id, {})
        rows.append({
            "id": q.id, "num": q.num, "text": q.text, "type": q.type.value,
            "options": q.options, "multi_select": q.multi_select,
            "references": q.references,
            "baseline": q.baseline, "baseline_choices": q.baseline_choices,
            "baseline_note": q.baseline_note,
            "comment_prompt": q.comment_prompt, "comment_baseline": q.comment_baseline,
            "answer": None if a is None else {
                "value": a.value, "choices": a.choices, "comment": a.comment,
                "updated_at": a.updated_at,
            },
            # One entry per answer component: "answer" always, plus
            # "comment" where a multiple-choice question had a note beside it.
            "comparison": {
                part: {"verdict": comp.verdict, "summary": comp.summary,
                       "detail": comp.detail, "model": comp.model,
                       "deterministic": comp.is_deterministic,
                       "created_at": comp.created_at}
                for part, comp in parts.items()
            },
        })
    notes = [{"id": n.id, "body": n.body, "updated_at": n.updated_at}
             for n in db.scalars(select(Note).where(Note.candidate_id == cid)
                                 .order_by(Note.created_at))]
    return {"id": c.id, "name": c.name, "email": c.email, "status": c.status.value,
            "submitted_at": c.submitted_at, "questions": rows, "notes": notes}


@router.post("/candidates/{cid}/compare", status_code=202)
def run_comparison(cid: int, background: BackgroundTasks, db: Session = Depends(get_db),
                   _: str = Depends(require_admin)) -> dict:
    c = db.get(Candidate, cid)
    if c is None:
        raise HTTPException(404, "no such candidate")
    background.add_task(comparison_service.compare_candidate, cid)
    return {"queued": True, "candidate_id": cid}


@router.post("/candidates/{cid}/notes", status_code=201)
def add_note(cid: int, payload: NoteIn, db: Session = Depends(get_db),
             _: str = Depends(require_admin)) -> dict:
    if db.get(Candidate, cid) is None:
        raise HTTPException(404, "no such candidate")
    n = Note(candidate_id=cid, body=payload.body)
    db.add(n)
    db.commit()
    db.refresh(n)
    return {"id": n.id, "body": n.body}


@router.get("/prompt")
def get_prompts(db: Session = Depends(get_db), _: str = Depends(require_admin)) -> dict:
    rows = list(db.scalars(select(Prompt).order_by(Prompt.version.desc())))
    active = next((p for p in rows if p.is_active), None)
    return {
        "active": None if active is None else
                  {"id": active.id, "version": active.version, "body": active.body},
        "versions": [{"id": p.id, "version": p.version, "is_active": p.is_active,
                      "created_at": p.created_at} for p in rows],
    }


@router.post("/prompt", status_code=201)
def new_prompt(payload: PromptIn, db: Session = Depends(get_db),
               _: str = Depends(require_admin)) -> dict:
    """Never edits in place. A new version is written and made active, so any
    comparison already stored still points at the prompt that produced it."""
    latest = db.scalar(select(Prompt).order_by(Prompt.version.desc()))
    for p in db.scalars(select(Prompt).where(Prompt.is_active.is_(True))):
        p.is_active = False
    p = Prompt(version=(latest.version + 1) if latest else 1,
               body=payload.body, is_active=True)
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"id": p.id, "version": p.version}
