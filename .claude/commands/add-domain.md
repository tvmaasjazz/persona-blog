---
description: Scaffold a new backend domain across libs/ and apps/api/
argument-hint: <domain-name> [quirks or notes in quotes]
---

Scaffold the `$1` domain. Notes on this domain: $2

You design the domain and brief the agents that write it: `schema-coder` for tables,
`fastapi-coder` for application code, and `be-test-writer` for tests. Don't write those
files yourself. None of the agents see this conversation, so every brief carries the
decisions it needs.

## Before briefing any agent

1. Check whether `libs/$1/` or `apps/api/domains/$1/` already exists. If either does,
   stop and tell me rather than merging into it.
2. From the notes, work out what this domain actually needs: which tables, which
   service methods, whether it talks to an LLM, whether it has settings. Ask me at
   most one question if something essential is genuinely ambiguous. Otherwise make a
   reasonable call and note it in your summary.

## Create

**1. Tables.** If the domain owns tables, hand them to the `schema-coder` agent first.
It writes the SQL, the revision, and the Orm classes, and verifies them. Pass each
table's columns (type, nullability, default), constraints, indexes, and enum types.
Wait for its report; the application code uses the Orm classes it creates. Skip if the
domain owns no tables.

**2. Application code.** Hand the rest to the `fastapi-coder` agent. Pass the domain
name, the entities and their fields with each request field's required, length and
format limits, each service method's signature and behaviour, the routes with their
status codes and errors, and the Orm classes from step 1. Ask for the files the
domain needs from this list:

- `libs/$1/`
  - `services.py` — `$1`'s service class, framework-free, dependencies via `__init__`;
    a `services/` package with one module per class if the domain has more than one
  - `services/<domain>_validation_service.py` — `<Domain>ValidationService`, only if a
    route needs a payload check that reads the database or compares more than one
    field (`fastapi-structure.md` ›
    Services › Validation guards). It makes `services/` a package
  - `inputs.py` — one `Input` model per method taking a structured payload
  - `results.py` — one `Result` per method, named after the method
  - `settings.py` — only if the domain has tunable values
  - `constants.py` — only if the domain has values that must not be overridden
  - `types.py` — only if the domain has enums; all of them go here
  - `tasks.py` — only if the domain has work that runs after a response
  - `prompts.py` — only if the domain calls an LLM; a `prompts/` package, one module per
    class, once it has more than one (`fastapi-structure.md` › Prompts)
  - `exceptions.py` — only if the domain needs exceptions callers must tell apart
  - `states.py`, a `graphs/` package and a `<Domain>NodeService` in `services/` — only
    if the domain's work is a graph, laid out as `fastapi-structure.md` › LangGraph
    workflows describes, including `output_formats.py` when a step's output must follow
    a format. A second graph for an existing domain is a folder under that
    domain's `graphs/`, and needs no new domain at all
- `apps/api/domains/$1/`
  - `dtos.py` (request field limits as `StringConstraints` aliases,
    `fastapi-structure.md` › DTOs › Inbound), `dependencies.py`, and `router.py`.
    Validation guard functions
    (`validate_<what>`) live in `dependencies.py`
- Wiring: the router in `apps/api/app_factory.py`, and the settings model on
  `AppSettings` in `apps/api/core/config.py`

If its report lists a schema change under "Follow-up needed", send that back to
`schema-coder`, then return to `fastapi-coder` for the code that depends on it.

**3. Tests.** Once the code exists, hand off to the `be-test-writer` agent. Pass it the
new source files, each service method and route, and the intended behaviour from the
notes: error cases, status codes, limits.

## After

Report as a list: files created, decisions you made where the notes were thin, and
anything the rules files didn't cover. Include the schema-coder's Verification and
Follow-up sections, the fastapi-coder's Judgement calls and Contradictions sections,
and the be-test-writer's Coverage, Test run, and Source problems sections. If a quirk of this domain conflicts with an
existing rule, say so and propose wording — don't quietly deviate.

Stop before running migrations or committing.
