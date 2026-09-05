# Threat model

Scope: one FastAPI process serving a tutoring API and a dashboard, plus an MCP
server that shares the same graph and database. SQLite for state, ChromaDB for
curriculum retrieval. Single tenant.

## What it holds

| Asset | Where | Why it matters |
|---|---|---|
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | `.env` | Billable; the endpoint spends them per request |
| `API_KEY` | `.env`, and the operator's browser tab | Gates the tutor endpoint |
| Student records and session logs | SQLite (`tutor.db`) | Names, ages, grades, mastery — data about minors |

`.env` and `*.db` are gitignored; CI fails if either is tracked.

## Threats

### T1 — Open, paid endpoint *(was open)*

`/api/v1/tutor/solve` ran model calls for any caller with an unbounded task.
**Controls.** `X-API-Key` in constant time; `task` capped; production refuses
the placeholder key. **Residual.** One shared key; no per-caller quota.

### T2 — Fabricated retrieval *(was open)*

The vector store was seeded and never queried; retrieval was keyword matching
over four hardcoded sentences. **Controls.** Retrieval queries ChromaDB and
reports its source; the keyword path is a labelled fallback. See
[ADR 0001](adr/0001-the-rag-actually-retrieves.md).

### T3 — Prompt injection through the task and the profile

The student's task and profile fields go into the model prompts, and the
retrieved curriculum is added to the doubt-resolver prompt. A crafted task can
shape the model's output.

**Controls.** Output is returned as data, never executed; the frontend escapes
everything it renders (both the transcript and the model reply — a task could
make the model echo HTML). **Residual.** A misleading lesson or quiz is
possible; nothing here reviews content before it reaches the student.

### T4 — Cross-site / cross-origin

`allow_origins=["*"]` with credentials, and the page rendered user and model
text with `innerHTML` unescaped. **Controls.** CORS is an allowlist; the page
is same-origin; all rendered values pass through `escapeHtml`.

### T5 — Error and provider detail leaking

`detail=str(e)` returned provider and internal text. Errors now carry a
correlation id; the detail is logged.

### T6 — Data about minors

Student records persist in SQLite with no encryption beyond filesystem
permissions and no retention policy. This is stated, not solved: deploy with a
database whose access and retention meet the applicable rules.

### T7 — Supply chain

Twelve unpinned packages, one imported by nothing. Everything is pinned;
`pip-audit`, `bandit` and gitleaks run in CI; the container runs as uid 10001.

## Not addressed

- No rate limit or per-caller quota.
- No review step on generated lessons, quizzes or parent reports.
- Student data is not encrypted at rest beyond filesystem permissions.
- Nothing here has been run against a model provider.
