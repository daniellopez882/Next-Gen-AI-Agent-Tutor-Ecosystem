# ADR 0002 — The tutor endpoint is authenticated and bounded; one place builds models

**Status:** accepted

## Context

`POST /api/v1/tutor/solve` runs LangGraph plus crewai — several paid model
calls — on every request. It accepted any caller, with no limit on `task`,
answered failures with `detail=str(e)`, and allowed any browser origin
(`allow_origins=["*"]` with `allow_credentials=True`). Anyone who could reach
the port could spend the operator's API credit.

`llm_config.py` built three near-identical clients, each hardcoding
`claude-3-5-sonnet-20240620` (retired) and `gpt-4o`, and returned
`ChatOpenAI(openai_api_key="mock_key")` with no key configured — an object
that constructs and then fails deep inside crewai.

## Decision

- `X-API-Key`, constant-time, on the tutor route. Production refuses to start
  on the placeholder key (`validate_production` in the lifespan).
- `task` is capped; the student profile is validated (id pattern, age range).
- Errors return a correlation id; the detail goes to the log.
- CORS is a configured allowlist, and the app serves its own page, so the
  browser calls it same-origin and needs no wildcard.
- `llm.py` is the single place models are built. Graph nodes that call
  `.invoke()` get a LangChain model; crewai agents get crewai's own `LLM` with
  the key passed explicitly (crewai rebuilds its client from `os.environ`, so a
  key that lives only in settings never reaches it otherwise). Model names come
  from configuration; `set_langchain_factory` / `set_crew_factory` are the
  seams the tests use.
- The six JSON extractions (`.replace('```json','')` + `json.loads`) are one
  extractor that tolerates prose around the JSON and never raises.

## Consequences

The suite runs with no provider key and no network. `database.init_db()` and
the ChromaDB seed, which were import side effects, run at startup instead.
