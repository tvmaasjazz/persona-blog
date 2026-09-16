---
description: Scaffold a new backend domain across libs/ and apps/api/
argument-hint: <domain-name> [quirks or notes in quotes]
---

Scaffold the `$1` domain. Notes on this domain: $2

Follow `.claude/rules/fastapi-structure.md` and `.claude/rules/python-naming.md` for
every file. Do not restate those conventions back to me — apply them.

## Before writing anything

1. Check whether `libs/$1/` or `apps/api/domains/$1/` already exists. If either does,
   stop and tell me rather than merging into it.
2. From the notes, work out what this domain actually needs: which tables, which
   service methods, whether it talks to an LLM, whether it has settings. Ask me at
   most one question if something essential is genuinely ambiguous. Otherwise make a
   reasonable call and note it in your summary.

## Create

**`libs/database/orm/<entity>.py`** for each new table, exported from
`libs/database/orm/__init__.py`. Skip if the domain owns no tables.

Each new package folder below gets an empty `__init__.py`.

**`libs/$1/`**
- `services.py` — `$1`'s service class, framework-free, dependencies via `__init__`
- `inputs.py` — one `Input` model per method taking a structured payload
- `results.py` — one `Result` per method, named after the method
- `settings.py` — only if the domain has tunable values
- `constants.py` — only if the domain has values that must not be overridden
- `types.py` — only if the domain has enums; all of them go here
- `prompts.py` — only if the domain calls an LLM
- `exceptions.py` — only if the domain needs exceptions callers must tell apart; each
  subclasses one standard exception from `libs/core/exceptions.py`

**`apps/api/domains/$1/`**
- `dtos.py` — `<Entity>Dto` shared by POST/PUT with `to_input()`; `<Entity>ResponseDto`
  with `from_result()` for GET routes only. Create, update and delete use the shared
  DTOs in `core/dtos.py`.
- `dependencies.py` — service factory plus its `Annotated` alias
- `router.py` — thin routes only

**Wire it up**
- Register the router in `apps/api/app_factory.py`
- Add the settings model to `AppSettings` in `apps/api/core/config.py`

**Migrations** — follow the `db-migration` skill: for each new table, a `.up.sql` and
`.down.sql` under `migrations/sql/<table>/` with the shared columns every table
carries, plus the revision wrapper in `migrations/revisions/`. Chain `down_revision`
to the current head.

**Tests** — once every file above exists, hand off to the `test-writer` agent. Don't
write tests yourself. It doesn't see this conversation, so pass it the new source
files, each service method and route, and the intended behaviour from the notes:
error cases, status codes, limits.

## After

Report as a list: files created, decisions you made where the notes were thin, and
anything the rules files didn't cover. Include the test-writer's Coverage, Test run,
and Source problems sections. If a quirk of this domain conflicts with an
existing rule, say so and propose wording — don't quietly deviate.

Stop before running migrations or committing.
