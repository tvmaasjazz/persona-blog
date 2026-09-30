# Generate-text engine

The step after step 13 of the original build plan (in `plan.md`'s git history before the persona outline), going off that plan's script. Step 13 proved one
hardcoded graph. This makes the graph a function of what the caller asked for, records
every run and step in Postgres, and sets the shape a second text type will follow.

## What changes for a caller

`POST /generate-text/blog-post` takes a payload that says what to write and which steps
to run:

```json
{
  "prompt_text": "Why sourdough starter needs a feeding schedule",
  "persona_info": "Writes plainly, bakes at home, distrusts jargon.",
  "additional_context": "Reference: https://example.com/starter-guide ...",
  "options": {
    "outline": { "is_enabled": true, "is_auto_approved": true },
    "draft": { "is_auto_approved": false },
    "humanize": { "is_enabled": true, "is_auto_approved": false }
  }
}
```

The options decide the topology: an enabled step becomes a node, and a step that isn't
auto-approved gets a review node after it. `draft` has no `is_enabled` because a blog
post without a draft is not a blog post.

`persona_info` is a text blob standing in for what the persona feature will later
generate as a summary. `additional_context` is likewise a blob: links, pasted text,
whatever the writer has. Both go to the prompts as they are.

## Layering

Generation endpoints live in the `generate_text` domain, one route per text type, not
in a domain per type. Creating a blog post record from a finished run is ordinary CRUD
in a blog-post domain, and that arrives with the feature that needs it.

```
libs/generate_text/
├── types.py                        GenerateTextNodeType, run and step status types
├── states.py                       GenerateTextState
├── inputs.py                       GenerateTextInput, StepOptionInput, resume input
├── results.py                      GenerateTextRunResult and the writers' results
├── settings.py                     max_rewrite_passes, checkpoint_ttl_minutes
├── services/
│   ├── generate_text_run_service.py    writes pb_generate_text_run, rollup included
│   ├── generate_text_step_service.py   writes pb_generate_text_step, rollup included
│   ├── generate_text_instrumentation_service.py  wraps a node in step records
│   ├── generate_text_node_service.py   builds the nodes
│   └── generate_text_service.py        starts and resumes runs
└── graphs/
    ├── base_generate_text_graph_builder.py      the abstract builder
    ├── generate_text_graph_builder_registry.py  text type → its builder
    └── blog_post/                  graph_builder.py, prompts.py, inputs.py

apps/api/domains/generate_text/     all three routes, one router, one dtos.py
```

A text type is not a lib of its own. It is a folder under `graphs/` holding a builder,
its prompts and its options — the engine writes blog posts; turning a finished run into
a blog post row is a different feature's concern.

`GenerateTextGraphBuilderRegistry` holds one builder per text type and raises
`NotImplementedError` for a type without one. `BlogPostGraphBuilder` extends
`BaseGenerateTextGraphBuilder`, carrying its `graph_name` and `graph_version` as class
attributes. `GenerateTextService` asks the registry for the builder and calls
`build_graph` on it; the version check on resume compares the run's stored version with
the builder's, which is what makes running two versions across a deploy a later feature
rather than a rewrite.

## The graph a builder produces

```
START → [generate_outline] → [review_outline] → generate_draft → [review_draft] → [humanize] → [review_humanize] → END
              ↑ rejected ──── rewrite_outline ←┘
```

Every reviewable step gets two extra nodes: a review node that calls `interrupt()`, and
a rewrite node the rejection routes to. A rewrite is its own node because it is its own
prompt — the original output plus the feedback — and may run on a different tier than
the step that produced the draft. The rewrite edges back into its review node, so a
reviewer can reject twice, bounded by `max_rewrite_passes`.

Which tier each step and rewrite uses belongs to the text type's graph definition, not
the payload. A caller chooses which steps run; the text type knows how each is done.

## Instrumentation

Every node is wrapped before it is added to the graph:

```python
graph_node = instrumentation_service.instrument(GenerateTextNodeType.GENERATE_DRAFT, node)
```

The wrapper writes a `RUNNING` step row with the next `step_number`, runs the node, then
marks the row `SUCCEEDED` or `FAILED` with its duration. It writes nothing to the run
itself: the newest step row is where the run sits. Each write is its own committed transaction, the rule `pb_llm_call` already
follows, so a run that fails still has its trail.

It re-raises LangGraph's `GraphBubbleUp` before its `except Exception`, because an
interrupt is how a review node pauses: the first version caught it and recorded every
paused run as failed. The paused step row is picked back up when the graph resumes, so
one pause is one step rather than two.

Two services under it, each writing one table: `GenerateTextRunService` and
`GenerateTextStepService`. Each rolls up as part of the transitions it already writes —
a step when it completes, a run when it completes, fails or pauses for review, which is
exactly when someone is looking at what it has cost. Rollups run synchronously in their
own transaction: one indexed aggregate over a handful of `pb_llm_call` rows, and a node
cannot reach `BackgroundTasks` anyway.

## Tables

`pb_generate_text_run`, `pb_generate_text_step`, and two columns on `pb_llm_call` that
were deliberately deferred until runs existed.

### `pb_generate_text_run`

| Column | Type | Notes |
| --- | --- | --- |
| `text_type` | `pb_text_type NOT NULL` | new enum type, `BLOG_POST` |
| `graph_name` | `TEXT NOT NULL` | |
| `graph_version` | `TEXT NOT NULL` | refusing a resume across versions depends on it |
| `status` | `pb_generate_text_run_status_type NOT NULL DEFAULT 'PENDING'` | `PENDING`, `RUNNING`, `AWAITING_REVIEW`, `COMPLETED`, `FAILED`, `CANCELLED` |
| `prompt_text` | `TEXT NOT NULL` | |
| `persona_info` | `TEXT` | |
| `additional_context` | `TEXT` | |
| `options` | `JSONB NOT NULL` | what the topology was built from; a resume reads it, never the resume payload |
| `error_code` / `error_message` | `TEXT` | Set only when no step owns the failure — a graph that never ran. A node's failure is recorded on its own step row |
| `llm_call_count` / `input_tokens` / `output_tokens` | `INTEGER NOT NULL DEFAULT 0` | rollups: zero is true before any call, unlike an unknown token count on `pb_llm_call` |
| `cost_usd` | `NUMERIC(16,10) NOT NULL DEFAULT 0` | |
| `started_at` / `finished_at` | `TIMESTAMP` | |

The run's own `identity` is the LangGraph thread id, so there is no separate column for
it, and there is no `current_step`: the newest step row answers that, and cannot go
stale the way a copy does. Where a run sits and what it produced come from two different
step rows — a run paused for review sits on its review step, whose own output is empty. Indexes: `(created_by_id, created_at DESC)` for a user's runs, and a partial on
`status` for in-flight ones.

### `pb_generate_text_step`

Same shape as the run's rollup columns, plus `run_id` (FK, cascade), `step_number`, `step_name`,
`attempt`, `status` (`RUNNING`, `SUCCEEDED`, `FAILED`, `SKIPPED`, `AWAITING_REVIEW`),
`input` / `output` JSONB, `duration_ms`, and the review columns: `human_decision`
(`APPROVED` / `REJECTED`), `human_feedback`, `decided_by_id`, `decided_at`.

`UNIQUE (run_id, step_number)` is what a replay depends on, and a retry is a new row with the
same `step_name` and `attempt` incremented.

### `pb_llm_call`

Gains `run_id` and `step_id`, both nullable, both `ON DELETE SET NULL` — a cost record
should outlive the run it belonged to. `LlmCompletionInput` carries them so a call links
itself; the instrumentation wrapper hands the step id to the node it wraps.

## Failing a run

`fail_run` is called from two places and they record different things. The
instrumentation wrapper calls it when a node raises: the step row holds the error, and
the run only changes status. `GenerateTextService._invoke_graph` calls it when the graph
itself breaks — an unreachable checkpointer, say — where no step exists to own the
error, so the run carries it. The first failure wins, because a node's exception passes
through both on its way out.

The graph is built before the run row is created, so options a text type can't read
leave nothing behind, and they raise `GenerateTextOptionsInvalidException` rather than
letting a pydantic error reach the route as a 500.

## What changed while building it

- A step's `output` column is JSONB, so a text step stores its text under a named key
  rather than assigning a bare string to a `dict` column.
- The state coerces UUIDs to `uuid.UUID`: asyncpg returns its own subclass, which
  LangGraph checkpoints as an unregistered type that a future version will refuse.
- The run's rollup aggregates `pb_llm_call` by `run_id` rather than summing step rows,
  so a call made outside a step still counts.
- `GenerateTextRunResult` is what `generate_text`, `resume_generate_text` and
  `find_generate_text_run` all return; each domain's `ResponseDto` projects the fields it
  exposes. Resume returns the run, not a second copy of the generated-text shape.

## Build order

1. The three tables' worth of schema: two new tables, the `pb_llm_call` columns, the new
   enum types, one migration.
2. The writer services and the instrumentation wrapper, with `LlmCompletionInput`
   carrying the run and step.
3. The engine: state, options, shared nodes, the graph service.
4. `libs/generate_text/graphs/blog_post/`: prompts per step and per rewrite, the
   builder and its version.
5. `apps/api/domains/generate_text/`, one router carrying all three routes.
6. Delete the step 13 route and its hardcoded graph, which this supersedes.
7. Tests, then a verification script covering a run with every step enabled, a rejection,
   and a resume.

## Deliberately not in this step

A second text type, though the registry is built for one. The persona feature behind
`persona_info`. A real un-AI-ify module behind `humanize`, which is a prompt pass for
now. Anything on the frontend. Resolving an older graph version at resume time, beyond
refusing it.
