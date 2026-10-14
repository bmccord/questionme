"""Load the questionnaire into the database.

    python seed.py /path/to/questions.json

The file is NOT in this repository and must not be added to it - it carries
the question text and the baseline answers. It lives outside the tree and is
passed in by path.

Re-running updates existing rows in place rather than deleting them, so
seeding again after a wording fix does not orphan anyone's answers.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db import SessionLocal, engine                     # noqa: E402
from app.models import Base, Question, QuestionType         # noqa: E402


def load(path: Path) -> list[dict]:
    items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise SystemExit(f"{path}: expected a non-empty JSON array")
    return items


def main(path: Path) -> None:
    Base.metadata.create_all(engine)
    items = load(path)
    db = SessionLocal()
    added = updated = 0
    try:
        for position, item in enumerate(items, start=1):
            is_mc = item.get("type") == "mc"
            baseline = item.get("baseline")
            comment = item.get("comment") or {}

            fields = dict(
                position=position,
                num=item["num"],
                source_num=item.get("sourceNum", item["num"]),
                text=item["text"],
                type=QuestionType.mc if is_mc else QuestionType.text,
                options=item.get("options"),
                multi_select=bool(item.get("multiSelect")),
                baseline=None if is_mc else baseline,
                baseline_choices=baseline if is_mc else None,
                baseline_note=item.get("baselineNote"),
                comment_prompt=comment.get("prompt"),
                comment_baseline=comment.get("baseline"),
                references=item.get("references"),
            )

            row = db.get(Question, item["id"])
            if row is None:
                db.add(Question(id=item["id"], **fields))
                added += 1
            else:
                for k, v in fields.items():
                    setattr(row, k, v)
                updated += 1
        db.commit()
    finally:
        db.close()

    mc = sum(1 for i in items if i.get("type") == "mc")
    no_baseline = [i["num"] for i in items if i.get("baseline") in (None, [], "")]
    print(f"  {added} added, {updated} updated, {len(items)} total")
    print(f"  {mc} multiple choice")
    print(f"  {len(no_baseline)} without a baseline: {', '.join(no_baseline)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]).expanduser())
