# questionme API

FastAPI + SQLAlchemy against MariaDB. One process, no worker queue - the
comparison runs as a FastAPI background task, which is enough for a handful of
candidates and one reviewer.

## Running locally

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env && chmod 600 .env      # fill it in
docker run -d --name qm-mariadb -p 13306:3306 \
  -e MARIADB_ROOT_PASSWORD=devroot -e MARIADB_DATABASE=questionme_dev \
  -e MARIADB_USER=questionme_dev -e MARIADB_PASSWORD=devpass mariadb:12
.venv/bin/python seed.py ~/Projects/questionme-data/questions.json
.venv/bin/uvicorn app.main:app --reload --port 8300
```

The seed file is **not in this repository**. It holds the question text and
the baseline answers and is passed in by path.

## Health

| path | checks |
|---|---|
| `/healthz` | the process is alive |
| `/readyz`  | a real `SELECT 1` through the app's own connection pool |

`/readyz` is the one worth monitoring. A liveness check that passes while the
application cannot reach MariaDB is exactly the blind spot that lets a
database outage look healthy.

## Things that are the way they are on purpose

**A skipped answer is NULL, not `""`.** "Declined to answer" and "answered
with nothing" are different facts. Only the first is excluded from the
comparison.

**The candidate endpoint cannot leak the baseline.** `QuestionPublic` has no
baseline field at all, so it is not a matter of remembering to filter.

**Candidate tokens come from `secrets.token_urlsafe`, never the database.**
MariaDB's `UUID()` is version 1: timestamp plus MAC address. Two consecutive
calls differ only in the low timestamp digits, so one candidate's link would
reveal the shape of everyone else's.

**Multiple choice never reaches Claude.** Set equality is exact and free;
asking a model to compare two strings that must match exactly only introduces
a way to be wrong. The optional comment beside the selection *is* sent, as its
own `comparison` row with `part = "comment"`.

**Comparison prompts are append-only rows.** Editing writes a new version;
each comparison records the version that produced it, so results stay
comparable across time.

**`resp.content[0]` is not the text.** The model may emit a thinking block
first. Always take the first block whose type is `text`.
