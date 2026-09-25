# Generate-text engine

The step after `plan.md`'s step 13, going off that plan's script. Step 13 proved one
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
libs/generate_text/                 the engine, text-type agnostic
├── types.py                        GenerateTextNodeType, run and step status types,
│                                   HumanDecisionType
├── states.py                       GenerateTextState
├── inputs.py                       GenerateTextInput, StepOptionInput, resume input
├── results.py                      GenerateTextRunResult, run and step results
├── settings.py                     max_rewrite_passes, checkpoint_ttl_minutes
├── services/
│   ├── generate_text_run_service.py    writes pb_generate_text_run, nothing else
│   ├── generate_text_step_service.py   writes pb_generate_text_step, nothing else
│   ├── generate_text_rollup_service.py aggregates llm calls into steps and runs
│   ├── generate_text_instrumentation_service.py  wraps a node in step records
│   ├── generate_text_node_service.py   the shared nodes
│   ├── generate_text_graph_service.py  text type → its registered graph
│   └── generate_text_service.py        starts and resumes runs
└── graphs.py                       GenerateTextGraphSpec: what a text type registers

libs/blog_post/                     one text type: prompts, topology, version
├── prompts.py                      BlogPostPrompt, per step and per rewrite
├── inputs.py                       BlogPostOptionsInput
├── graphs.py                       build_blog_post_graph + build_blog_post_graph_spec
└── constants.py                    BLOG_POST_GRAPH_NAME, BLOG_POST_GRAPH_VERSION

apps/api/domains/generate_text/     POST /generate-text/blog-post
apps/api/domains/generate_text_runs/ GET and POST .../{run_identity}/resume
```

`GenerateTextGraphService` holds a map of text type to the graph registered for it, and
raises `NotImplementedError` for a type without one. A text type registers itself —
`build_blog_post_graph_spec(...)` returns its name, current version and builder, and the
dependency factory passes the map in — so the engine imports no text type. Building it
the other way round produced a genuine import cycle, which is why the rule now says so.
The lookup takes a graph version from the start, even though only the current version
resolves today: running two versions side by side across a deploy is the feature that
needs it, and a signature with no room for it is the hard part to add later.

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

The wrapper writes a `RUNNING` step row with the next `seq`, points the run's
`current_step` at it, runs the node, then marks the row `SUCCEEDED` or `FAILED` with its
duration. Each write is its own committed transaction, the rule `pb_llm_call` already
follows, so a run that fails still has its trail.

It re-raises LangGraph's `GraphBubbleUp` before its `except Exception`, because an
interrupt is how a review node pauses: the first version caught it and recorded every
paused run as failed. The paused step row is picked back up when the graph resumes, so
one pause is one step rather than two.

The three services under it each do one thing: `GenerateTextRunService` writes the run
table, `GenerateTextStepService` writes the step table, and `GenerateTextRollupService`
sums the `pb_llm_call` rows of a finished step into that step, and the steps of a
finished run into the run. Rollups run synchronously in their own transaction: a step's
rollup is one indexed aggregate over a handful of rows, and a node cannot reach
`BackgroundTasks` anyway. If the run-level rollup ever costs too much, the route can
schedule it, which is the one place background work exists.

## Tables

`pb_generate_text_run`, `pb_generate_text_step`, and two columns on `pb_llm_call` that
were deliberately deferred until runs existed.

### `pb_generate_text_run`

| Column | Type | Notes |
| --- | --- | --- |
| `text_type` | `pb_text_type NOT NULL` | new enum type, `BLOG_POST` |
| `graph_name` | `TEXT NOT NULL` | |
| `graph_version` | `TEXT NOT NULL` | refusing a resume across versions depends on it |
| `thread_id` | `TEXT NOT NULL UNIQUE` | the LangGraph thread |
| `status` | `pb_generate_text_run_status_type NOT NULL DEFAULT 'PENDING'` | `PENDING`, `RUNNING`, `AWAITING_REVIEW`, `COMPLETED`, `FAILED`, `CANCELLED` |
| `current_step` | `TEXT` | |
| `prompt_text` | `TEXT NOT NULL` | |
| `persona_info` | `TEXT` | |
| `additional_context` | `TEXT` | |
| `options` | `JSONB NOT NULL` | what the topology was built from; a resume reads it, never the resume payload |
| `error_code` / `error_message` / `error_step` | `TEXT` | |
| `llm_call_count` / `input_tokens` / `output_tokens` | `INTEGER NOT NULL DEFAULT 0` | rollups: zero is true before any call, unlike an unknown token count on `pb_llm_call` |
| `cost_usd` | `NUMERIC(16,10) NOT NULL DEFAULT 0` | |
| `started_at` / `finished_at` | `TIMESTAMP` | |

Indexes: `(created_by_id, created_at DESC)` for a user's runs, a partial on `status` for
in-flight runs, and the unique on `thread_id`.

### `pb_generate_text_step`

Same shape as the run's rollup columns, plus `run_id` (FK, cascade), `seq`, `step_name`,
`attempt`, `status` (`RUNNING`, `SUCCEEDED`, `FAILED`, `SKIPPED`, `AWAITING_REVIEW`),
`input` / `output` JSONB, `duration_ms`, and the review columns: `human_decision`
(`APPROVED` / `REJECTED`), `human_feedback`, `decided_by_id`, `decided_at`.

`UNIQUE (run_id, seq)` is what a replay depends on, and a retry is a new row with the
same `step_name` and `attempt` incremented.

### `pb_llm_call`

Gains `run_id` and `step_id`, both nullable, both `ON DELETE SET NULL` — a cost record
should outlive the run it belonged to. `LlmCompletionInput` carries them so a call links
itself; the instrumentation wrapper hands the step id to the node it wraps.

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
4. `libs/blog_post/`: prompts per step and per rewrite, the builder, the version.
5. `apps/api/domains/generate_text/` and `apps/api/domains/generate_text_runs/`.
6. Delete the step 13 route and its hardcoded graph, which this supersedes.
7. Tests, then a verification script covering a run with every step enabled, a rejection,
   and a resume.

## Deliberately not in this step

A second text type, though the registry is built for one. The persona feature behind
`persona_info`. A real un-AI-ify module behind `humanize`, which is a prompt pass for
now. Anything on the frontend. Resolving an older graph version at resume time, beyond
refusing it.
