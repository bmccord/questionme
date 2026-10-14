# questionme

A doctrinal questionnaire for a preacher search. Candidates receive a private
link, answer at their own pace, and submit once. An admin console reviews the
answers, compares them against a baseline, and can ask Claude to analyse the
free-form responses.

**Prototype.** This is deliberately small and direct. It will eventually be
absorbed into another platform and rewritten; nothing here is built for that
future.

## What is not in this repository

The questionnaire text, the baseline answers, and the comparison prompt. This
repository is public; that content is not. It lives in the database, seeded
from a file kept outside this tree, and the prompt is stored and versioned in
the database so it can be edited without a deploy.

## Layout

```
api/   Python (FastAPI) - the whole backend, including the Claude integration
ui/    Angular - candidate form and admin console
```

## Running it

See `api/README.md` and `ui/README.md`.
