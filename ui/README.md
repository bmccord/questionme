# questionme UI

Angular 22, standalone components, signals, zoneless. Two apps in one bundle,
split by route:

```
/q/:token      the candidate form - no login, the token is the credential
/admin         dashboard, candidate detail, comparison review
```

## Running locally

```sh
nvm use                 # .nvmrc pins 24.21.0; Angular 22 needs >= 24.15
npm install
npm start               # http://localhost:4200, /api proxied to :8300
```

The API must be running on port 8300. See `../api/README.md`.

## Notes on the candidate form

**Typing is never blocked on the network.** Edits land in a local draft
signal immediately and are saved on a 600 ms debounce. Saves are grouped per
question with `groupBy` so a fast typist on question 7 cannot have their work
reordered behind an in-flight request for question 6.

**The reference panel.** Thirteen sub-parts ask "Why or why not?" and q13a
opens "If your answer to question (12) is yes…". Those questions carry a
`references` array, and the form shows the referenced question - with
whatever the candidate has already said - in a highlighted panel above the
one they are answering, plus a link to jump back to it.

**Submission names what is blank.** The confirmation dialog lists every
unanswered question number as a clickable chip, because the lock is
irreversible and a candidate who skipped nine by accident should be able to
see that before agreeing.

**After submission the same link still works**, read-only, so a candidate can
always see what they sent.
