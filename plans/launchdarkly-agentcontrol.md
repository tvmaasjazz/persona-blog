# LaunchDarkly AgentControl — plan

The goal: change which model each generation step uses, and what it's prompted with, in a
deployed environment from the LaunchDarkly dashboard, with no deploy and no restart.
This plan starts with how generation works today, then what AgentControl offers. It ends
with levels of integration, from simplest to fullest, and the steps for the first one.

Local copies of the LaunchDarkly docs and notes on the SDK source, fetched 2026-11-06, are in
`.reference/launchdarkly/` (start at `INDEX.md`). Where the docs and the SDK source
disagree, the source notes (`sdk-source-notes.md`) win.

## How generation works today

### The graph

`libs/generate_text/graphs/blog_post/graph_builder.py` builds one LangGraph `StateGraph`
per run from the run's options. Outline and humanize are optional, draft always runs, and
each step is followed by a review loop unless it's auto-approved:

```
START
  → GENERATE_OUTLINE  (FAST)                 optional
      → REVIEW_OUTLINE ⇄ REWRITE_OUTLINE (FAST)        unless auto-approved
  → GENERATE_DRAFT    (STRONG, Markdown format)
      → REVIEW_DRAFT ⇄ REWRITE_DRAFT (STRONG)          unless auto-approved
  → HUMANIZE          (STRONG, Markdown format)  optional
      → REVIEW_HUMANIZE ⇄ REWRITE_HUMANIZE (STRONG)    unless auto-approved
  → END
```

- **Review** nodes call `interrupt()`. The run is checkpointed to Redis and can sit for
  hours, then resume in another process. A rejection routes to the step's rewrite node,
  up to `max_rewrite_passes`.
- **The graph's shape is pinned per run** by `graph_version`. A run built on an older
  version is refused on resume (`GenerateTextRunVersionMismatchException`), so changing
  the shape breaks paused runs. Changing a prompt or a model doesn't.
- **`GenerateTextInstrumentationService`** wraps every node, so each pass is a
  `psg_generate_text_step` row with its duration, its status, and its charge to the user.

### Where the model is chosen

1. **The step picks a tier, in code, when the graph is built.** The builder passes an
   `LlmType` to each node: `FAST` for outline and its rewrite, `STRONG` for draft,
   humanize and their rewrites. Steps share a tier, so draft and humanize can't use
   different models today.
2. **The tier picks a model, from settings, when the process starts.** `LlmSettings`
   (`libs/llm/settings.py`) maps each tier to `provider`, `model_name`,
   `max_output_tokens`, `request_timeout_seconds` and `reasoning_effort`. Changing one
   means an env var (`LLM__STRONG__MODEL_NAME`) and a restart.
3. **Only OpenAI is wired up.** `LlmProviderType.ANTHROPIC` exists and `anthropic` is a
   dependency, but `build_llm_service` registers only `OpenAiLlmService`, which calls the
   Responses API.
4. **Every tier's model must have a price.** `LlmSettings` refuses to load if a tier's
   model has no `model_pricing` entry, because a call's `cost_usd` comes from that table,
   and a step's charge to the user is that cost times the credit markup.

### Where the prompt is built

- One `Prompt` class per step (`graphs/blog_post/prompts/`) builds a system prompt and a
  user prompt from `UPPER_SNAKE` templates in Python `str.format` syntax. The rewrite is a
  second method on the same class, and it shares the system prompt.
- **Conditional sections are built in code.** `_build_persona_prompt_section` and the
  other helpers return `""` when there's nothing to say, and each step picks which persona
  fields it uses. For example, outline uses name, bio and background, and humanize uses
  writing style and sample.
- **Draft and humanize put the Markdown format rules in their system prompt.** The rules
  come from `BLOG_POST_BODY_FORMAT_RULES`, the same module that validates the output.
  `GenerateTextNodeService._complete_with_output_format` validates the output, retries
  with the problems added to the prompt, and raises once it's out of retries.

### What every call records

`LlmService._complete` writes a `psg_llm_call` row before the call and fills it in after.
The row holds the tier, provider, model, purpose (the node type), both prompts, the
response, token counts, cost and duration. The run's and step's totals roll up from these
rows. **This table stays the source of truth for billing**, whatever LaunchDarkly shows.

## What AgentControl offers

What matters for this app, checked against the docs and SDK source (`.reference/launchdarkly/`):

- **A config** is one LaunchDarkly resource per LLM call site. Each config holds variations,
  and each variation is a model plus its parameters and either **messages** (completion
  mode) or **instructions** (agent mode). Targeting rules pick the variation per
  *context*, such as a user. **A config's mode can't be changed after it's created.**
- **Changes reach a running server within seconds.** The SDK streams flag data into an
  in-memory store. If LaunchDarkly goes down, the server keeps serving the last values it
  had. A process that *starts* during an outage has nothing to serve unless we give it a
  persistent store (Redis works) or fall back to code defaults.
- **There are two Python SDKs:**
  - **`launchdarkly-ai-server` 1.0.0** is current. Its main path is "LaunchDarkly calls
    the model for you" (`config().invoke()` with provider handlers). It has no fallback
    value: `invoke()` raises when the config is off or LaunchDarkly can't be reached. It's
    tested only on Python 3.12, and we run 3.14.
  - **`launchdarkly-server-sdk-ai` (`ldai`)** is the legacy SDK, in maintenance mode. It
    returns the config with a default you pass, plus a tracker you report tokens,
    duration and success to. It's tested on 3.14.
- **We can keep making the call ourselves.** Our LLM layer does retries, format
  validation and `psg_llm_call` logging, and it needs to keep doing them. The current SDK
  supports this two ways:
  - `inspect_config(key, context)` returns the raw config and never raises.
  - A **custom handler** (`create_handler`) wraps our own call. The SDK times it, reads
    the token usage it returns, and records success or error as LaunchDarkly metrics.
- **Templating is limited in the current SDK.** It fills only plain `{{variable}}`
  placeholders, with no Mustache sections such as `{{#var}}...{{/var}}`, and no spaces
  inside the braces. Context attributes go under `ldContext`; the docs also show `ldctx`
  and `ld_context`, and the source is right. So the conditional sections stay in code, and
  are passed in as variables already built.
- **Metrics come in per variation:** generations, latency, tokens, error rate, cost, and
  feedback (a thumbs up or down we report). LaunchDarkly computes cost from our token
  counts times *its own* model price table, which can drift from ours.
- **Prompt snippets** are versioned pieces of text, referenced as
  `{{snippet.key#version}}` and filled in on LaunchDarkly's side. No SDK code is needed.
- **Agent skills** are versioned Markdown files. Only the Claude-agents and OpenCode
  handlers load them automatically.
- **Judges** are LLM-as-judge configs that score an output from 0 to 1 at a sampling rate.
  Each one is an extra LLM call we pay for, and can run in the background.
- **Agent graphs** hold a root agent, agent-mode configs as nodes, and edges with handoff
  JSON. LaunchDarkly doesn't execute them. Level 3 covers what that means for us.
- **Experiments** split variations by context and compare the metrics above. They come
  with the Foundation plan and up.
- **Guarded rollouts** need Enterprise with the Guardian add-on.
- **Pricing:** one "AI run" is one tracked call, and a judge evaluation is another. The
  free Developer plan includes AgentControl. Its limits are under *Free plan budget*.

## Who makes the LLM call

**LaunchDarkly never calls a model.** Whichever SDK path we take, the call goes from our
process to OpenAI or Anthropic with our own API keys. The two paths differ only in whose
code makes it:

- **LaunchDarkly's handler makes the call.** `config().invoke()` routes to a handler
  package, such as `launchdarkly-ai-openai-messages`, which calls the provider's SDK.
  The current SDK steers toward this path.
- **We make the call.** We read the config, call through `LlmService`, and report usage
  back, either through a custom handler that wraps our call or through the legacy
  tracker. This was the documented pattern for the legacy SDK, and the current SDK
  still supports it.

**Nothing LaunchDarkly shows is lost when we make the call,** as long as we report usage.
Monitoring, experiments, cost per variation, feedback and judges all run on the events
we send.

What we give up is the handler packages' conveniences, none of which this app uses
today:

- Their mapping of LaunchDarkly parameters to the provider's request. We map them
  ourselves and validate them.
- Structured output set in the dashboard.
- Inline judges. We can run judges ourselves.
- Tool-call tracking.
- Time to first token when streaming.

What we keep is everything `LlmService` does: retries, refusal and truncation mapping,
the format-fix loop, the `psg_llm_call` row, and the cost that users are charged.

**The model list in the dashboard is a catalog, not what can run.**

- LaunchDarkly offers a long list of models, and you can add custom ones. The list is
  only metadata: it suggests parameters and prices the cost charts.
- Either way, the models that actually work are the ones whose provider is wired into
  our code and has a key. We also need a price for each one, or users can't be charged
  for it.
- The LangChain handler packages cover any provider LangChain supports, but each
  provider still needs its own package and key. Using them means adopting LangChain's
  chat models in place of our provider services, which costs more than writing
  `AnthropicLlmService`.
- **For wide model choice later,** a gateway such as OpenRouter gives many models
  behind one key and one OpenAI-style API, as one more provider service.
- **Restrict the dashboard's list** (Project settings › AI model configs › Restrict) to
  the models we run and price, so it can't offer one that would only fall back.

## Levels of integration

Each level builds on the one before it, and each one is useful on its own.

### Level 0 — Per-step models in settings (no LaunchDarkly)

Map each step to a model in `LlmSettings`, instead of each tier, so draft and humanize
can differ. Changing a model still needs an env var and a restart, and changing a prompt
still needs a deploy.

It's an hour's work, and Level 1 needs it anyway as its fallback. It doesn't give "on the
fly" on its own.

### Level 1 — Model and system prompt per step, from LaunchDarkly (recommended start)

**What you get:** in the dashboard, for outline, draft and humanize separately, you pick
the model and its parameters, and edit the system prompt. Changes reach a running server
within seconds, and LaunchDarkly shows latency, tokens and error rate per variation. If
LaunchDarkly is off, unreachable, or serves something we can't use, the step runs exactly
as it does today.

**What's in LaunchDarkly:**

- **Three completion-mode configs:** `blog-post-outline`, `blog-post-draft` and
  `blog-post-humanize`. Each rewrite uses its step's config, as it uses its step's tier
  today.
- **Each variation is a model plus one system message,** such as:

  ```
  Write a complete blog post draft from the outline and brief provided. Write the
  full prose, ready for review — not another outline.

  {{format_rules}}{{persona_section}}{{tone_and_audience_section}}
  ```

- **User prompts stay in code.** They carry the material for the call (the brief, the
  outline, the previous output and the feedback), not the style.
- **Variables are built in code and passed in:**
  - `format_rules`: the Markdown rules, from the same module that validates them.
  - `persona_section`, `tone_and_audience_section` and `additional_context_section`:
    already built, `""` when empty, with each step still choosing which persona fields
    to use.
- **The context is the user,** keyed by their `identity`, with `role` as an attribute.
  No email, name or persona text goes to LaunchDarkly. Targeting by user is enough to
  try a prompt on your own runs first.

**What changes in code:**

1. **A config service in `libs/llm/` that resolves a step's config.**
   - **Input:** a config key, the context, the variables, and the step's code default
     (its tier and its system template).
   - **Result:** the provider, the model settings (the `LlmTierSettings` fields), the
     rendered system prompt, and the variation's key and version.
   - **It falls back to the code default, and logs why, when any of these is true:**
     - LaunchDarkly is off, unreachable, or the config is disabled.
     - The provider isn't one we have a service for.
     - The model has no entry in `model_pricing`. We can't bill a model we can't price,
       so our price table is the allowlist of models.
     - A parameter fails validation.
     - The template leaves a `{{...}}` unfilled.
     - The template drops `{{format_rules}}` for a step that has an output format, so the
       prompt can't drift from the check.
2. **Prompt classes return the system prompt's variables, not the finished text.** They
   also return the default system template and the finished user prompt.
   - The current system constants become the defaults, rewritten in `{{variable}}`
     syntax.
   - `LlmService` renders whichever template wins with one renderer, so a default and a
     served template can't render differently.
   - The user templates are unchanged.
3. **Nodes take a config key and a default, in place of `LlmType`,** and pass both, with
   the variables, to `LlmService` on every call. Nothing is resolved when the graph is
   built, so a paused run picks up changes, and a config change never touches
   `graph_version`.
4. **`LlmService` does the rest.** It asks `LlmConfigService` for the config,
   LaunchDarkly or default, in place of looking a tier up. It then runs the provider call
   inside that service's tracking wrapper, which reports duration, tokens and success to
   LaunchDarkly. Pricing, retries and the `psg_llm_call` row are unchanged.
   - A config is resolved per call, which is cheap because it's read from memory. A
     format retry could therefore land on a new variation if one is published that
     second, and that's accepted.
   - Resolving stays a service of its own, beside `LlmService` and not inside it, because
     it's a different job (`fastapi-structure.md` › Services). Nodes still talk only to
     `LlmService`.
5. **`psg_llm_call` gets three nullable columns:** `config_key`, `config_variation_key`
   and `config_variation_version`. Every call can then be traced to the variation that
   wrote it. Calls that used the code default leave them null.
6. **Settings and wiring:**
   - **Whether LaunchDarkly is used is an explicit setting,** never inferred from
     whether a key is present (`fastapi-structure.md` › Settings).
     - `LaunchDarklySettings.is_enabled` defaults to `false` in code, and is overridden
       by `LAUNCHDARKLY__IS_ENABLED`.
     - The SDK key is a secret, so it lives on `AppSettings` as `launchdarkly_sdk_key`,
       set only by the env var `LAUNCHDARKLY_SDK_KEY`.
     - `LaunchDarklySettings` and `TelemetrySettings` belong to no single domain, so they
       live in `libs/core/settings.py` beside `BackgroundJobSettings`.
     - Enabled with no key refuses to start.
     - Disabled means no client is created and every step uses its default.
   - **Tests always run with it off.** The test settings set it off, so a developer's
     `.env` with LaunchDarkly on never makes the suite connect.
   - The client is created in `lifespan.py` with a short init timeout, and closed (which
     flushes events) on shutdown.
   - **If LaunchDarkly can't be reached at startup,** with a key set, the app logs it and
     carries on with defaults; it never stops. A missing key is the refuse-to-start case
     above, since that's a configuration mistake rather than an outage.
7. **The prompt content is kept out of telemetry:** `capture_content=False` on the
   handler, and generative AI message content capture stays off in OpenTelemetry. Prompts
   carry persona text and briefs, and `psg_llm_call` already holds them. LaunchDarkly also
   becomes the app's observability backend, covered under Observability below.

**Which SDK:** start with the current `launchdarkly-ai-server`, through `inspect_config`
plus a custom handler, with our wrapper supplying the fallback it lacks. Before building on
it, run a short spike on 3.14: install it, read a config, run one tracked call, and check
the event lands in Monitoring. If it fails on 3.14, use the legacy `ldai` instead. It
fits this design just as well (a default, a tracker), but it's in maintenance mode. The
service in item 1 keeps the choice behind one class either way.

**New dependencies** (to approve): `launchdarkly-server-sdk` and `launchdarkly-ai-server`
(or `launchdarkly-server-sdk-ai`). The OpenTelemetry packages come later, with Phase 2.

**One client per process:** build the base `ldclient` ourselves in `lifespan.py`, and
hand it to the AI SDK with `init_client(client=...)`. Feature flags and AgentControl
then share one connection. We also get to choose its timeout and a Redis persistent
store, which the AI SDK's own client wouldn't let us do.

### Level 2 — More providers, real feedback, experiments

Each of these is its own PR, in roughly this order:

- **Styles a user picks.** For example, a creator picks "standard" or "advanced" per
  step when starting a run.
  - Each style is its own config: `blog-post-draft` and `blog-post-draft-advanced`, and
    the same for each step. Which model and prompt each style uses stays in LaunchDarkly.
  - Which styles exist is in code: an enum, with an option on each step in
    `BlogPostOptionsInput`. The frontend lists the enum, options validation rejects an
    unknown style, and the run saves the choice in its options, so a resume uses the same
    style.
  - The node maps the style to its config key. Each style has its own code default too,
    so the fallback stays meaningful.
  - The charge follows the actual model's price, as it does today, so an advanced run
    costs what it costs without any special handling. Showing a price estimate before
    the run starts would need Later › *Credit holds*.
  - **Why separate configs rather than one config targeted on a context attribute:**
    - The code picks the key, so a targeting mistake can't quietly serve the wrong style.
    - Each style gets its own monitoring.
    - Experiments stay within one style.
- **The Anthropic provider.** `AnthropicLlmService` beside `OpenAiLlmService`, with its
  prices in `model_pricing`, so a variation can switch a step to Claude. This also covers
  the Anthropic client that Later › *Models per request* needs.
- **Review decisions as feedback.** When a reviewer approves or rejects a step, report
  positive or negative feedback against the variation that wrote it. Its key and version
  are already on the `psg_llm_call` row from Level 1. This gives each variation an
  approval rate, the most honest quality signal the app has, and it costs nothing to
  collect.
- **Experiments.** Split variations by user and compare approval rate, rewrite count,
  tokens and latency. This needs the Foundation plan. A run's variation can change
  between a step and its rewrite only if the targeting changes mid-run, and that's
  accepted.
- **Separate rewrite configs.** Use these if a rewrite should use a different model or
  user prompt from its step:
  - `blog-post-draft-rewrite` and the other two rewrite configs.
  - The shared system text moves into a **prompt snippet** that both configs reference.
    Each config is then two messages, a system one and a user one, which makes the user
    templates editable too.
- **A judge on humanize output.** Sampled, in the background, scoring for AI tells. It
  pairs with Phase 3 › *Humanization*. Each judgement is a paid LLM call and a billed AI
  run, so keep the sampling rate low. It isn't charged to the user.
- **A persistent store in Redis.** A process that starts during a LaunchDarkly outage
  then serves the last known configs, not code defaults.

### Level 3 — Steps and their order from LaunchDarkly

**Agent graphs aren't a fit for this app's flow:**

- **LaunchDarkly holds the topology only.** It doesn't execute a graph, keep its state,
  or pause it. Nothing in a graph can express "stop here until a human approves".
- **The SDK's graph runners don't fit.**
  - `graph()` lets the model choose each handoff.
  - `to_lang_graph()` builds a `StateGraph` whose state is just `messages`, with no
    checkpointer and no interrupts.
  - The legacy `create_agent_graph` calls itself experimental and not ready for
    production.
- **We'd still write every part that matters:** a builder that turns the served topology
  into our `StateGraph`, adding the review and rewrite loops, the output format per node,
  and the user's step options.
- **A paused run would break if the topology changed under it.** Avoiding that means
  storing the resolved topology on the run when it starts and rebuilding from that copy
  on resume. That replaces `graph_version` as the thing that pins a run's shape.
- **The nodes must be agent-mode configs,** and a config's mode is fixed at creation.

**What it would buy:** adding, removing or reordering steps without a deploy. That's
mostly what Phase 3 › *Humanization* wants ("possibly as several calls…, try adding or
removing steps").

**A narrower way to get that:**

- An ordinary **LaunchDarkly JSON feature flag** holds the humanize pass list, such as
  `["humanize-cut-filler", "humanize-rhythm"]`. Each entry is a Level 1 config key.
- The run reads the flag once, when it starts, and saves the list in its options. A
  paused run keeps its shape that way.
- The builder adds one node per pass.

That covers the experiment the plan wants, at a fraction of the cost. Revisit full agent
graphs only if the steps become dynamic beyond humanize.

### Skills, and how they differ from prompts

- **A skill is versioned Markdown,** delivered as a reference that the app fetches. It
  isn't specific to Claude. Only the Claude-agents and OpenCode handlers load skills on
  their own, though: an agent runtime reads a skill when the task calls for it. A plain
  OpenAI Responses call can't do that.
- **So for us, a skill is fetched text appended to the system prompt,** exactly like
  writing more prompt. What a skill adds is versioning, reuse across configs, and an
  audit trail.
- **Prompt snippets give us the same, with no code.** LaunchDarkly fills them in before
  the config reaches us. The humanize rubric, the outline structure guidance and similar
  text fit as snippets.
- **Skills only make sense if a step moves to an agent runtime** that loads skills on
  demand, such as a humanize agent with tools.

## Observability

LaunchDarkly Observability replaces Logfire as the app's telemetry backend: traces,
logs, errors and metrics for the whole app, not just LLM calls. Logfire was chosen but
never wired up, so nothing has to be removed. Building it is plan.md › Phase 2 ›
*Logging and tracking*. This plan only settles where the data goes.

- **Every process uses LaunchDarkly: the API and the generation workers.** It's not
  just for AgentControl. The API will use feature flags, and possibly migration flags.
  So every process holds an SDK client, and telemetry goes through LaunchDarkly's
  observability plugin (`ldobserve`), registered on that same client.
- **What the plugin adds over plain OpenTelemetry sent to LaunchDarkly's endpoint:**
  - **Flag data on spans is the same either way.** The plugin's flag data comes from
    LaunchDarkly's OpenTelemetry tracing hook (`ldotel`, with `include_value=True`).
    That hook adds each flag and config evaluation as an event on the current span, and
    it can be added to a client without the plugin.
  - **The plugin wires everything for us:** the tracer, the logger and the OTLP
    exporter, OpenTelemetry's auto-instrumentation, log export and log correlation.
  - **It fetches sampling configuration from LaunchDarkly** (its `backend_url`), which
    suggests sampling can be tuned in the dashboard. Confirm before relying on it.
  - **It has an `observe` singleton** for manual errors, metrics and logs.
  - Since every process holds a client anyway, the plugin costs no extra service
    connections. That was the only argument against it.
- **One wrapper owns the choice of backend:** `configure_telemetry(settings, ld_client)`
  in `apps/api/core/telemetry.py`, called once at startup.
  - **Where telemetry goes is its own setting,** never inferred from whether a key is
    present. `TelemetrySettings.exporter` is a `TelemetryExporterType`, overridden by
    `TELEMETRY__EXPORTER`:
    - `NONE`: nothing is exported, and logs only go to the terminal. This is the
      default in code (`TelemetrySettings`), and what tests use.
    - `LAUNCHDARKLY`: registers the plugin on the client. Settings refuse it unless
      LaunchDarkly is enabled.
    - `OTLP`: plain OpenTelemetry to `TelemetrySettings.otlp_endpoint`, with the `ldotel`
      hook on the client when there is one. With no endpoint set, it refuses to start.
    - `TelemetryExporterType` lives in `libs/core/types.py`.
  - **The two settings are independent.** For example, LaunchDarkly can be on for flags
    and AgentControl while telemetry is `NONE` locally. Production sets both by env
    var, and so does a local `.env` while developing against LaunchDarkly.
  - **Code never imports `ldobserve`.** A custom span uses `opentelemetry.trace`, a log
    uses structlog, and an error is recorded on the current span. So moving to plain
    OpenTelemetry, or another backend, replaces only this wrapper. Then the `ldotel` hook
    goes on the client directly, and the standard `OTEL_EXPORTER_OTLP_ENDPOINT` points
    wherever we like.
- **Logging keeps structlog, routed through stdlib `logging`.** The goal is clean logs
  in the terminal locally and searchable logs in LaunchDarkly when deployed. structlog's
  contextvars are the simplest way to put the request ID and run ID on every line, which
  Phase 2 › *Logging and tracking* asks for. Dropping structlog would mean
  `extra={...}` at every call site and a filter to do the same job.

  The plugin's log export only captures stdlib `logging` records, so `apps/api/core/logging.py`
  changes from rendering straight to the console to this:

  - **structlog's last processor is `render_to_log_kwargs`.** It hands each event to
    stdlib with its fields as `extra`, which OpenTelemetry's handler turns into log
    attributes we can search in LaunchDarkly.
  - **A console handler renders every stdlib record with structlog:** a
    `ProcessorFormatter` with `ExtraAdder` in its `foreign_pre_chain`.
    - Dev gets `ConsoleRenderer`: coloured, one line per event, fields shown.
    - Deployed environments get `JSONRenderer` to stdout. Railway's log view keeps
      working, and stdout doesn't count against LaunchDarkly's log quota.
    - Logs from granian, SQLAlchemy and httpx come out in the same format, which they
      don't today.
  - **The plugin adds its own handler** for export to LaunchDarkly.
    - **Ordering gotcha:** the plugin sets up default logging before it instruments, so
      configure logging first, then register the plugin.
    - Check in that PR that a log's fields arrive as attributes, not stringified into
      the message.
- **One LaunchDarkly client per process,** shared by flags, AgentControl and
  observability. The AI SDK gets it through `init_client(client=...)`.
- **To check before building:**
  - That the plugin and the OpenTelemetry instrumentations it pulls in run on Python
    3.14.
  - Which libraries it auto-instruments (FastAPI, SQLAlchemy, Redis, httpx).
  - How it records errors, and how LaunchDarkly groups them in its Errors view.
  - Whether the sampling it fetches can be set in the dashboard.

## Free plan budget

The Developer plan is $0 and "never billed": at a limit, LaunchDarkly stops taking that
kind of data until the month resets. Running out doesn't cost money, but it does leave us
blind for the rest of the month. Confirm in the first PR that configs keep being *served*
once AI runs hit their cap, and that only the metrics stop.

| Limit | Free each month | What uses it here | Fits? |
| --- | --- | --- | --- |
| **Service connections** | 5 | One per server-side SDK instance per environment, summed over the month. Every process with a client counts, and so do pre-production environments. | **Tightest.** See below |
| AgentControl AI runs | 5K | One per tracked LLM call. A post makes 3 to 6, more with rewrites, plus any judge runs. | About 800 to 1,600 posts |
| Trace spans | 10M | Every request makes several, and status polling every 2s during a run makes most of them. | Yes, with the trims below |
| Log lines | 10M | Exported logs only; stdout doesn't count. | Yes, at INFO |
| Errors captured | 5K | Exceptions. | Yes |
| Client-side MAU | 1K | Only if the frontend uses LaunchDarkly's JS SDK. | Keep it off the frontend |
| Session replays | 5K | Only with browser observability. | Not planned |

**Service connections are a monthly pool of connected time, not a cap on how many run
at once.** One connection is one SDK client connected to one environment for a whole
month (43,800 minutes), and partial months add up without rounding. The free 5 are about
219,000 connection-minutes a month, spent across every environment however we like.
For example:

- 10 clients for half a month is 5.
- A few hours of local dev, then a burst in staging, then production, all draw from the
  same pool.

**Who holds a client: every process,** the API and the generation workers, for flags,
AgentControl and observability (Observability). Every granian worker process is its own
client, so count processes, not replicas.

**Production, plus local dev while building it.** Both are turned on by settings
(Observability, Level 1 › Settings and wiring).

- **Local dev uses its own LaunchDarkly environment,** such as `development`, with its
  own SDK key and targeting. Trying a prompt or flag locally then never changes what
  production serves. Its connected time comes out of the same pool.
- **CI and tests always run with LaunchDarkly off.**
- **Once the integration is built,** local dev can go back to the defaults, and a
  prompt or model change is tried in production by targeting your own user first, then
  everyone. That's how LaunchDarkly expects changes to be tested.
- **The math:**
  - Two API instances and two generation workers, each one process running all month,
    is 4 connections.
  - That leaves about 1 for local dev. That's plenty: a dev server running 8 hours a
    day is about a third of a connection, and that's per granian process, so use one
    worker locally too.
  - A staging environment running all month, or a fifth process, means the paid plan.

To stay under 5:

- **One client per process,** shared by flags, AgentControl and observability (Level 1's
  `init_client(client=...)`). Letting the AI SDK build a second client would double the
  count.
- **LaunchDarkly off in tests and CI,** so they never connect.
- **One granian worker per API instance,** since the app is async, and one process per
  generation worker instance.
- **Autoscaling over a fixed count.** An instance added for a busy week is about a
  quarter of a connection.
- **Polling mode doesn't help.** For Python, 732 polls count as one connection. Polling
  every 30 seconds is about 118 connections a month per process, and polling slowly
  enough to cost less loses "on the fly".
- **Past 5, it's a paid plan.** Check the Foundation price per service connection when
  that's close.

**Trace spans.** Only the polling volume matters:

- Each poll is a request span, plus the FastAPI instrumentation's internal ASGI
  send and receive spans, plus a Redis session read and a few queries: about 8 to 10 spans.
- Turn the ASGI internal spans off (`exclude_spans=["receive", "send"]`), and sample the
  poll and health check routes.
- A traffic spike, such as a bot, could still use up the month's spans. Phase 2 ›
  *Rate limiting* covers that.

**Client-side MAU.** Signed-out readers would each count as a monthly active user, and
1K goes quickly. Any flag the frontend needs is evaluated on the backend and returned by
the API.

## Level 1 steps

**One PR, or two if the spike is separate.**

1. **Before any code:**
   - Create the three configs, in completion mode. Give each a variation that copies
     today's model and system prompt, and target everyone to it, so switching on changes
     nothing.
2. **The spike:** install the SDK on 3.14 and run a throwaway script that reads
   `blog-post-draft` and runs one tracked call through a custom handler. Then pick the
   SDK. Add the dependencies with Tyler's approval, then run `uv lock`.
3. **The schema:** the three `psg_llm_call` columns (`schema-coder`).
4. **The placement review.** Tyler reviews this list before any coder starts:
   - `libs/llm/services/llm_config_service.py`: `LlmConfigService`. It resolves a config
     key into the model settings and rendered system prompt, falling back to the code
     default, and wraps a call to report metrics. It delegates to a provider-style config
     source:
     - `BaseLlmConfigSourceService`: the contract.
     - `LaunchDarklyLlmConfigSourceService`: the LaunchDarkly source.
     - `DefaultLlmConfigSourceService`: always serves the defaults, for when
       LaunchDarkly is off and in tests.

     This follows `fastapi-structure.md` › Services: a provider with no HTTP surface
     stays inside the lib whose contract it implements, as with
     `openai_llm_service.py`.
   - **Template rendering:** a `PromptTemplateUtils` in `libs/llm/utils/`, with
     `{{name}}` substitution and a check for unfilled placeholders.
   - **`libs/generate_text/`:** prompt classes, node service and graph builder, changed in
     place.
   - **Wiring:** `apps/api/lifespan.py` (the client), `apps/api/core/config.py` (the
     settings), and `apps/api/core/dependencies.py` (`build_llm_service`).
5. **The code** (`fastapi-coder`): the config service, then the `LlmService` and node
   changes, then the prompt classes.
6. **The tests** (`be-test-writer`):
   - The fallback cases in Level 1's item 1, each one.
   - The renderer.
   - Default templates render byte-for-byte as today's prompts do.
   - One test with a stubbed source that serves a different model and prompt, checking
     both reach the provider call and the new `psg_llm_call` columns.
7. **A script, `backend/scripts/llm_config_check.py`.** It prints what each step resolves
   to (source, model, variation, and the rendered system prompt for a sample persona), so
   a dashboard change can be checked without starting a run.

**Rules to update with this PR** (proposed wording comes with it):

- **`langgraph.md` › Prompts:**
  - A step's system template may be served by `LlmConfigService`.
  - The module constant is its default, in `{{name}}` syntax.
  - A served template gets everything conditional as a variable that's already built,
    and the format rules always as a variable, never written into the template.
- **`langgraph.md` › LangGraph workflows:** a node passes its config key and default to
  `LlmService` when it runs, and nothing is resolved when the graph is built.

**Docs that name Logfire** change with the Observability PR, not this one:

- **CLAUDE.md › Non-obvious stack choices:** `structlog → Logfire` becomes
  `structlog → OpenTelemetry → LaunchDarkly Observability`.
- **`pytest-testing.md`:** "Logfire export" in the not-tested table becomes "telemetry
  export".

## To decide

- **Completion or agent mode for the configs.** Completion fits single calls and gets
  judges in the UI everywhere. Agent mode is needed only for Level 3 agent graphs, which
  this plan advises against. **Recommended: completion.**
- **Whether a paused run picks up a prompt change before its rewrite.** Recommended: yes,
  since the variation is recorded on every call. The alternative is pinning each step's
  resolved config in the checkpoint.
