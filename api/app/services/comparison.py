"""Compare a candidate's answers against the baseline.

Rules that shape this file:

1. Multiple choice never reaches Claude. Same option or different option is a
   set comparison - exact, free, instant, and incapable of hallucinating about
   something that has one correct answer. Only free text and the optional
   comment on an MC question are sent.

2. Skipped is not a verdict about content. An answer whose value is NULL is
   recorded as `not_answered` without an API call.

3. Cross-references are resolved before sending. A candidate who writes
   "see #14" is making a reasonable move on a 122-question form, and a model
   that sees only those three words will score it as evasive.

4. Questions are compared in parallel. Sequentially a full candidate took
   about ten minutes, which is long enough that the admin page looks broken.
   Each worker owns its own database session; nothing is shared but plain
   data loaded up front.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal
from ..models import Answer, Candidate, Comparison, Prompt, Question

log = logging.getLogger(__name__)

REF = re.compile(r"#(\d+[a-z]?)\b", re.I)
MAX_WORKERS = 6

FALLBACK_PROMPT = """You are helping evaluate candidates for a preaching position \
by comparing their answers to a doctrinal questionnaire against a baseline answer \
from a candidate who has already been interviewed.

Compare the CANDIDATE ANSWER to the BASELINE ANSWER for the same question.

Some questions are multiple choice with an optional comment box. For those, \
the selections are compared separately and what you are given is the comment \
each person wrote beside their choice. CONTEXT will say when that is the case.

Judge substance, not wording. Two answers that reach the same position by \
different reasoning agree. Two answers that use similar language to mean \
different things do not.

Reply with JSON only. `verdict` must be exactly one of the three strings; \
never null.
{"verdict": "match" | "partial" | "differs",
 "summary": "one sentence naming the actual difference, or stating they agree",
 "key_differences": ["..."],
 "notable": "anything a reviewer should see - a hedge, an unusual emphasis, \
a position held for a different reason - or null"}"""


# --- progress, so the admin page can show something honest -----------------
# One process, one reviewer: a module-level dict is enough. It is advisory -
# the authoritative state is always the comparison rows themselves.
_lock = threading.Lock()
_progress: dict[int, dict] = {}


def progress_for(candidate_id: int) -> dict:
    with _lock:
        return dict(_progress.get(candidate_id, {"running": False}))


def _start(candidate_id: int, total: int) -> None:
    with _lock:
        _progress[candidate_id] = {"running": True, "total": total, "done": 0,
                                   "started": time.time()}


def _tick(candidate_id: int) -> None:
    with _lock:
        p = _progress.get(candidate_id)
        if p:
            p["done"] = p.get("done", 0) + 1


def _finish(candidate_id: int) -> None:
    with _lock:
        p = _progress.get(candidate_id)
        if p:
            p["running"] = False
            p["finished"] = time.time()


# --- plain data, safe to hand to worker threads ----------------------------
@dataclass
class _Task:
    qid: str
    qnum: str
    qtext: str
    qtype: str
    options: list | None
    baseline: str | None
    baseline_choices: list | None
    comment_baseline: str | None
    their_value: str | None
    their_choices: list | None
    their_comment: str | None


def _mc_verdict(chosen: list | None, expected: list | None) -> str:
    chosen, expected = set(chosen or []), set(expected or [])
    if not chosen:
        return "not_answered"
    if not expected:
        return "no_baseline"
    return "match" if chosen == expected else "differs"


def _resolve_refs(text: str, said_by_num: dict[str, str]) -> str:
    if not text:
        return text
    extra = [f'[their answer to #{n}: "{said_by_num[n.lower()]}"]'
             for n in dict.fromkeys(REF.findall(text))
             if n.lower() in said_by_num]
    return text + ("\n\n" + "\n".join(extra) if extra else "")


def _ask(client, prompt_body: str, t: _Task, baseline: str, theirs: str,
         candidate_id: int, prompt_id: int | None, part: str) -> Comparison:
    context = ("CONTEXT: this is the comment each person wrote beside their "
               "multiple-choice selection, not a full answer.\n\n"
               if part == "comment" else "")
    msg = (f"{context}QUESTION: {t.qtext}\n\n"
           f"BASELINE ANSWER:\n{baseline}\n\n"
           f"CANDIDATE ANSWER:\n{theirs}")
    try:
        resp = client.messages.create(
            model=settings.anthropic_model, max_tokens=1024,
            system=prompt_body, messages=[{"role": "user", "content": msg}])
        # content[0] is not reliably the answer: the model may emit a thinking
        # block first, which has no .text at all.
        raw = next((b.text for b in resp.content
                    if getattr(b, "type", None) == "text"), "").strip()
        if not raw:
            raise ValueError("no text block in the response")
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
        data = json.loads(raw)
        verdict = data.get("verdict")
        if verdict not in ("match", "partial", "differs"):
            data = {**data, "_invalid_verdict": verdict}
            verdict = "unclear"
        return Comparison(candidate_id=candidate_id, question_id=t.qid, part=part,
                          prompt_id=prompt_id, verdict=verdict,
                          summary=data.get("summary"), detail=data,
                          model=settings.anthropic_model, is_deterministic=False)
    except Exception as exc:                       # noqa: BLE001
        log.exception("comparison failed for %s %s", t.qid, part)
        return Comparison(candidate_id=candidate_id, question_id=t.qid, part=part,
                          prompt_id=prompt_id, verdict="error",
                          summary=str(exc)[:500],
                          model=settings.anthropic_model, is_deterministic=False)


def _rows_for(t: _Task, client, body: str, prompt_id: int | None,
              candidate_id: int, said_by_num: dict[str, str]) -> list[Comparison]:
    rows: list[Comparison] = []
    if t.qtype == "mc":
        rows.append(Comparison(
            candidate_id=candidate_id, question_id=t.qid, part="answer",
            verdict=_mc_verdict(t.their_choices, t.baseline_choices),
            is_deterministic=True,
            summary=(None if not t.their_choices else
                     f"chose {t.their_choices}; baseline {t.baseline_choices}")))
        theirs, base, part = t.their_comment, t.comment_baseline, "comment"
    else:
        theirs, base, part = t.their_value, t.baseline, "answer"

    if theirs is None or not theirs.strip():
        # An unused optional comment box is not a finding.
        if part == "answer" or base:
            rows.append(Comparison(candidate_id=candidate_id, question_id=t.qid,
                                   part=part, verdict="not_answered",
                                   is_deterministic=True))
    elif not base:
        rows.append(Comparison(candidate_id=candidate_id, question_id=t.qid,
                               part=part, verdict="no_baseline",
                               is_deterministic=True))
    elif client is None:
        log.warning("no Anthropic key; skipping %s %s", t.qid, part)
    else:
        rows.append(_ask(client, body, t, base, _resolve_refs(theirs, said_by_num),
                         candidate_id, prompt_id, part))
    return rows


def _write(rows: list[Comparison], candidate_id: int, qid: str) -> None:
    db = SessionLocal()
    try:
        for row in rows:
            existing = db.scalar(select(Comparison).where(
                Comparison.candidate_id == candidate_id,
                Comparison.question_id == qid,
                Comparison.part == row.part))
            if existing:
                db.delete(existing)
                db.flush()
            db.add(row)
        db.commit()
    except Exception:                              # noqa: BLE001
        log.exception("could not store comparison for %s", qid)
        db.rollback()
    finally:
        db.close()


def compare_candidate(candidate_id: int, question_ids: list[str] | None = None) -> None:
    """Compare every question, or just the ones named.

    `question_ids` is how the admin console re-runs a single question after
    editing its baseline or the prompt, without paying for the other 121.
    """
    db = SessionLocal()
    try:
        c = db.get(Candidate, candidate_id)
        if c is None:
            return
        questions = list(db.scalars(select(Question).order_by(Question.position)))
        if question_ids:
            wanted = set(question_ids)
            questions = [q for q in questions if q.id in wanted]
        answers = {a.question_id: a for a in c.answers}
        prompt = _active_prompt(db)
        body, prompt_id = (prompt.body, prompt.id) if prompt else (FALLBACK_PROMPT, None)

        said_by_num = {}
        for q in list(db.scalars(select(Question))):
            a = answers.get(q.id)
            said = (a.value if a and a.value else None) or (
                ", ".join(a.choices) if a and a.choices else None)
            if said:
                said_by_num[q.num.lower()] = said

        tasks = []
        for q in questions:
            a = answers.get(q.id)
            tasks.append(_Task(
                qid=q.id, qnum=q.num, qtext=q.text, qtype=q.type.value,
                options=q.options, baseline=q.baseline,
                baseline_choices=q.baseline_choices,
                comment_baseline=q.comment_baseline,
                their_value=a.value if a else None,
                their_choices=a.choices if a else None,
                their_comment=a.comment if a else None))
    finally:
        db.close()

    client = None
    if settings.anthropic_api_key:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    _start(candidate_id, len(tasks))

    def run(t: _Task) -> None:
        try:
            _write(_rows_for(t, client, body, prompt_id, candidate_id, said_by_num),
                   candidate_id, t.qid)
        finally:
            _tick(candidate_id)

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            list(ex.map(run, tasks))
    finally:
        _finish(candidate_id)


def _active_prompt(db) -> Prompt | None:
    return db.scalar(select(Prompt).where(Prompt.is_active.is_(True)))
