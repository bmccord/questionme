"""Compare a candidate's answers against the baseline.

Three rules shape this file:

1. Multiple choice never reaches Claude. Same option or different option is a
   set comparison - exact, free, instant, and incapable of hallucinating about
   something that has one correct answer. Only the free-text answers and the
   optional comment on an MC question are sent.

2. Skipped is not a verdict about content. An answer whose value is NULL is
   recorded as `not_answered` without an API call.

3. Cross-references are resolved before sending. A candidate who writes "see
   #14" is making a perfectly reasonable move on a 122-question form, and a
   model that sees only those three words will score it as evasive.
"""
from __future__ import annotations

import json
import logging
import re

from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal
from ..models import Answer, Candidate, Comparison, Prompt, Question

log = logging.getLogger(__name__)

REF = re.compile(r"#(\d+[a-z]?)\b", re.I)

FALLBACK_PROMPT = """You are helping evaluate candidates for a preaching position \
by comparing their answers to a doctrinal questionnaire against a baseline answer \
from a candidate who has already been interviewed.

Compare the CANDIDATE ANSWER to the BASELINE ANSWER for the same question.

Some questions are multiple choice with an optional comment box. For those, the selections are compared separately and what you are given is the comment each person wrote beside their choice. CONTEXT will say when that is the case.

Judge substance, not wording. Two answers that reach the same position by \
different reasoning agree. Two answers that use similar language to mean \
different things do not.

Reply with JSON only. `verdict` must be exactly one of the three strings; never null.
{"verdict": "match" | "partial" | "differs",
 "summary": "one sentence naming the actual difference, or stating they agree",
 "key_differences": ["..."],
 "notable": "anything a reviewer should see - a hedge, an unusual emphasis, \
a position held for a different reason - or null"}"""


def _active_prompt(db) -> Prompt | None:
    return db.scalar(select(Prompt).where(Prompt.is_active.is_(True)))


def _resolve_refs(text: str, answers: dict[str, Answer], by_num: dict[str, Question]) -> str:
    """Inline any '#14' style reference so the model sees what was meant."""
    if not text:
        return text
    extra = []
    for num in set(REF.findall(text)):
        q = by_num.get(num.lower())
        if q is None:
            continue
        a = answers.get(q.id)
        said = (a.value if a and a.value else None) or (
            ", ".join(a.choices) if a and a.choices else None)
        if said:
            extra.append(f'[their answer to #{num}: "{said}"]')
    return text + ("\n\n" + "\n".join(extra) if extra else "")


def _mc_verdict(answer: Answer | None, q: Question) -> str:
    chosen = set(answer.choices or []) if answer else set()
    expected = set(q.baseline_choices or [])
    if not chosen:
        return "not_answered"
    if not expected:
        return "no_baseline"
    return "match" if chosen == expected else "differs"


def compare_candidate(candidate_id: int) -> None:
    """Runs in the background after submission, and again on demand."""
    db = SessionLocal()
    try:
        c = db.get(Candidate, candidate_id)
        if c is None:
            return
        questions = list(db.scalars(select(Question).order_by(Question.position)))
        answers = {a.question_id: a for a in c.answers}
        by_num = {q.num.lower(): q for q in questions}
        prompt = _active_prompt(db)
        body = prompt.body if prompt else FALLBACK_PROMPT

        client = None
        if settings.anthropic_api_key:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        for q in questions:
            a = answers.get(q.id)
            rows: list[Comparison] = []

            if q.type.value == "mc":
                # The selection: set equality, no API call.
                rows.append(Comparison(
                    candidate_id=c.id, question_id=q.id, part="answer",
                    verdict=_mc_verdict(a, q), is_deterministic=True,
                    summary=None if not (a and a.choices) else
                            f"chose {a.choices}; baseline {q.baseline_choices}",
                ))
                # The optional comment beside it: this is free text and gets
                # the same treatment as any other free-text answer.
                their_text = a.comment if a else None
                base_text = q.comment_baseline
                part = "comment"
            else:
                their_text = a.value if a else None
                base_text = q.baseline
                part = "answer"

            if their_text is None or their_text.strip() == "":
                # Only record a missing comment when there was a baseline
                # comment to miss; an unused optional box is not a finding.
                if part == "answer" or base_text:
                    rows.append(Comparison(candidate_id=c.id, question_id=q.id, part=part,
                                           verdict="not_answered", is_deterministic=True))
            elif not base_text:
                rows.append(Comparison(candidate_id=c.id, question_id=q.id, part=part,
                                       verdict="no_baseline", is_deterministic=True))
            elif client is None:
                log.warning("no Anthropic key; skipping %s %s", q.id, part)
            else:
                rows.append(_ask(client, body, q, base_text,
                                 _resolve_refs(their_text, answers, by_num),
                                 c.id, prompt, part))

            try:
                for row in rows:
                    existing = db.scalar(select(Comparison).where(
                        Comparison.candidate_id == c.id,
                        Comparison.question_id == q.id,
                        Comparison.part == row.part))
                    if existing:
                        db.delete(existing)
                        db.flush()
                    db.add(row)
                db.commit()
            except Exception:                      # noqa: BLE001
                # A bad row is one question's problem, not the run's.
                log.exception("could not store comparison for %s", q.id)
                db.rollback()
    finally:
        db.close()


def _ask(client, prompt_body: str, q: Question, baseline: str, theirs: str,
         candidate_id: int, prompt: Prompt | None, part: str) -> Comparison:
    context = ("CONTEXT: this is the comment each person wrote beside their "
               "multiple-choice selection, not a full answer.\n\n"
               if part == "comment" else "")
    msg = (f"{context}QUESTION: {q.text}\n\n"
           f"BASELINE ANSWER:\n{baseline}\n\n"
           f"CANDIDATE ANSWER:\n{theirs}")
    try:
        resp = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=prompt_body,
            messages=[{"role": "user", "content": msg}],
        )
        # content[0] is not reliably the answer: the model may emit a
        # thinking block first, which has no .text at all. Take the first
        # actual text block instead of assuming a position.
        raw = next(
            (b.text for b in resp.content if getattr(b, "type", None) == "text"),
            "",
        ).strip()
        if not raw:
            raise ValueError("no text block in the response")
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
        data = json.loads(raw)
        verdict = data.get("verdict")
        if verdict not in ("match", "partial", "differs"):
            # Record it rather than trusting it - a malformed verdict is a
            # fact about the run, and it must never reach a NOT NULL column.
            data = {**data, "_invalid_verdict": verdict}
            verdict = "unclear"
        return Comparison(
            candidate_id=candidate_id, question_id=q.id, part=part,
            prompt_id=prompt.id if prompt else None,
            verdict=verdict,
            summary=data.get("summary"), detail=data,
            model=settings.anthropic_model, is_deterministic=False,
        )
    except Exception as exc:                       # noqa: BLE001 - record, don't crash the run
        log.exception("comparison failed for %s", q.id)
        return Comparison(
            candidate_id=candidate_id, question_id=q.id, part=part,
            prompt_id=prompt.id if prompt else None,
            verdict="error", summary=str(exc)[:500],
            model=settings.anthropic_model, is_deterministic=False,
        )
