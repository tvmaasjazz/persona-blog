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
   service methods, which routes and the permission each needs, whether it talks to an
   LLM, whether it has settings. Ask me at most one question if something essential is
   genuinely ambiguous. Otherwise make a reasonable call and note it in your summary.
3. Design to the rules: read `.claude/rules/fastapi-structure.md`, and
   `.claude/rules/langgraph.md` if the domain has a LangGraph graph, LLM prompts or
   `OutputFormat`s.

## Create

**1. Tables and permissions.** If the domain owns tables, or its routes need
`PermissionType` members that don't exist yet, hand them to the `schema-coder` agent
first, briefed as the `db-migration` skill lists. A new permission is a schema change
(`database.md` › Enums): name each member and the roles that hold it. Wait for its
report; the application code uses the Orm classes and permissions it creates. Skip if
the domain needs neither.

**2. Application code.** Hand the rest to the `fastapi-coder` agent. Pass the domain
name, the entities and their fields with each request field's required, length and
format limits, each service method's signature and behaviour, the routes with their
permissions, status codes and errors, and the Orm classes from step 1. Say which of
these the domain needs, so the agent writes only those (`fastapi-structure.md` and,
for a graph or LLM work, `langgraph.md` give each its file): settings, constants,
enums, lib exceptions, LLM prompts, a validation guard, an after-response task, a
background job, an app-lifetime loop, a LangGraph graph. A second graph for an
existing domain is a folder under that domain's `graphs/`, not a new domain. Wiring is
the router in `app_factory.py` and the settings field on `AppSettings`.

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
