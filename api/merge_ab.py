"""One-off migration: fold each a/b question pair into a single question.

    python merge_ab.py            # report what would change
    python merge_ab.py --apply    # do it

Run this AFTER seeding the merged questions file - the combined question row
must exist before an answer can reference it, or the foreign key rejects the
insert. The order is:

    python seed.py /path/to/questions.merged.json    # adds q4, q8, q9 ...
    python merge_ab.py --apply                       # folds answers, drops a/b

It moves any existing candidate answers onto the new combined question, so
nobody loses work - 96 of the 122 question ids are unchanged and are never
touched at all.

A merged question's baseline is new, so every stored comparison for it is
stale by definition; those rows are deleted and should be re-run.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import delete, select                       # noqa: E402

from app.db import SessionLocal                             # noqa: E402
from app.models import Answer, Comparison, Question         # noqa: E402

APPLY = "--apply" in sys.argv


def join(a: str | None, b: str | None) -> str | None:
    """Combine the two halves the same way the question text was combined."""
    a = (a or "").strip() or None
    b = (b or "").strip() or None
    if a and b:
        head = a if a[-1] in ".!?:;)\"'" else a + "."
        return f"{head} {b}"
    return a or b


def main() -> None:
    db = SessionLocal()
    try:
        ids = {q.id for q in db.scalars(select(Question))}
        pairs = sorted({m.group(1) for qid in ids
                        if (m := re.fullmatch(r"q(\d+)a", qid))}, key=int)
        if not pairs:
            print("  nothing to merge - no a/b questions present")
            return

        missing = [f"q{n}" for n in pairs if f"q{n}" not in ids]
        if missing:
            print(f"  REFUSING: the merged questions are not seeded yet "
                  f"({len(missing)} missing, e.g. {missing[:3]}).")
            print("  Run:  python seed.py <questions.merged.json>  first.")
            raise SystemExit(1)

        moved = combined = dropped = 0
        for n in pairs:
            a_id, b_id, new_id = f"q{n}a", f"q{n}b", f"q{n}"
            rows = {}
            for ans in db.scalars(select(Answer).where(
                    Answer.question_id.in_([a_id, b_id]))):
                rows.setdefault(ans.candidate_id, {})[ans.question_id] = ans

            for cand_id, byq in rows.items():
                a, b = byq.get(a_id), byq.get(b_id)
                value = join(a.value if a else None, b.value if b else None)
                comment = (a.comment if a and a.comment else
                           (b.comment if b else None))
                if value is not None:
                    combined += 1
                if APPLY:
                    existing = db.scalar(select(Answer).where(
                        Answer.candidate_id == cand_id,
                        Answer.question_id == new_id))
                    if existing is None:
                        existing = Answer(candidate_id=cand_id, question_id=new_id)
                        db.add(existing)
                    existing.value = value
                    existing.choices = None
                    existing.comment = comment
                moved += 1

            if APPLY:
                # Stale by definition: the merged question has a new baseline.
                db.execute(delete(Comparison).where(
                    Comparison.question_id.in_([a_id, b_id, new_id])))
                db.execute(delete(Answer).where(
                    Answer.question_id.in_([a_id, b_id])))
                db.flush()
                for old in (a_id, b_id):
                    q = db.get(Question, old)
                    if q is not None:
                        db.delete(q)
                        dropped += 1

        if APPLY:
            db.commit()
        print(f"  pairs: {len(pairs)}")
        print(f"  candidate answers folded: {moved} rows -> {combined} combined")
        print(f"  old question rows removed: {dropped}")
        print("  APPLIED" if APPLY else "  DRY RUN - re-run with --apply")
    finally:
        db.close()


if __name__ == "__main__":
    main()
