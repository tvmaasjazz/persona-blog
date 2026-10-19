# Persona Blog — build plan

The outline from here on. Detail gets added to each step as it comes up.

1. **Persona CRUD — backend**
2. In parallel:
   - **Persona in generate text** — pass a persona into the generate text call and
     its prompts
   - **Persona CRUD — frontend**
3. **Blog post CRUD — backend**, in two PRs: Markdown output first (3a), then the
   `content_item` and `blog_post` tables and CRUD (3b)
4. **Blog post CRUD — frontend**
5. **Background runs and polling** — generation stops being tied to one HTTP request:
   the request starts a run, the run works in the background, and the frontend polls
   it. Details in Step 5 below
6. **Avatar upload** — replaces the avatar URL field with a real upload:
   - **Backend:** store images in S3 and add an upload route that returns the stored
     image's URL
   - **Frontend:** the persona form uploads the chosen image, then sends the returned
     URL as `avatar_url` on create or update
     6.a - voice to text + llm based endpoint to fill out the persona info sections?
     6b. - basic homepage which fetches a feed situation? like add feed and search? maybe save this for later after
     initial deploy, and add a fillerv fopr now or just gray it out and start with my personas
     6c - - **Usage plans:** an unlimited plan for the admin; a free plan of one persona and
     one blog post; and an extended trial the admin can grant to chosen users, of two
     personas and ten blog posts (figure out full user system and how to handle for now woith no payment but consider for later as well)
7. **Testing and fine tuning** — try adding or removing steps in the generate text
   process, different models, different prompts
8. **Logging** — proper logging for the endpoints and for the graph
9. **Log tracking service** — set it up and test it
10. **Initial deploy**, in two parts:
   - **Railway:** deploy the frontend and backend. Open question: a subdomain of an
     existing domain first, or a dedicated domain from the start

## Step 1 — Persona CRUD backend

Table `pb_persona`, on top of `BaseOrm`'s columns. The owner is `created_by_id`, the
same as `pb_generate_text_run`, so there's no separate `user_id`.

| Column                    | Type                | Notes                                                    |
| ------------------------- | ------------------- | -------------------------------------------------------- |
| `name`                    | text, required      | Pen name; unique per owner among live rows               |
| `bio`                     | text, required      | Short public summary                                     |
| `avatar_url`              | text, nullable      |                                                          |
| `background`              | text, nullable      | Backstory that shapes their view                         |
| `writing_style`           | text, nullable      | Sentence length, vocabulary, formatting habits           |
| `default_tone`            | text, nullable      | Prefills tone when asking the persona to write something |
| `default_target_audience` | text, nullable      | Prefills audience the same way                           |
| `sample_writing`          | text, nullable      | A passage in their voice for the model to imitate        |
| `is_public`               | bool, default false | Others can read the profile; later, persona search       |

Every field is open text. The frontend (step 2b) shows a description with an example for
each field.

Routes under `/personas`: create, list the caller's own, get, update, soft delete.

Access:

- **Read** — your own persona, or anyone's public one. Someone else's private persona
  is a 404, so its existence doesn't leak.
- **Update, delete** — the creator only. Someone else's public persona is a 403; their
  private one is still a 404.
- **List** — your own only, returned as `{"personas": [...]}`. No pagination yet.
  Browsing other users' public personas waits for persona search.

## Step 2a — Persona in generate text

The request names a persona; every step's prompt builds its own system and user prompt
from that persona's fields.

**Request.** `GenerateBlogPostDto` drops `persona_info` and gains:

| Field              | Type           | Notes                                                  |
| ------------------ | -------------- | ------------------------------------------------------ |
| `persona_identity` | UUID, required | One of the caller's own personas; anyone else's is 404 |
| `tone`             | text, nullable | The frontend prefills it from `default_tone`           |
| `target_audience`  | text, nullable | Prefilled from `default_target_audience`               |

**Before the graph.** A dependency, `get_generate_text_persona`, loads the persona on
its own short session and closes it before the route runs, so no connection sits idle
in a transaction while the graph waits on the LLM. The route passes the loaded persona
to `GenerateTextService.generate_text`. Generating as a persona is creator-only, even
for a public one: anyone else's is a 404.

**State.** The graph state holds primitives only, so the persona's fields go in flat
(`persona_name`, `persona_bio`, ...), and `state.build_persona()` groups them back into
a `GenerateTextPersonaInput`, the way `build_auth_user()` does. `tone` and `target_audience` go in beside
`prompt_text`.

**Prompts.** One class per step, extending `BaseGenerateTextPrompt`:
`BlogPostOutlinePrompt`, `BlogPostDraftPrompt`, `BlogPostHumanizePrompt`. Each has
`build_generate_prompt(state)` and `build_rewrite_prompt(state, previous_output,
feedback_text)`, both returning `BuildPromptResult(system_prompt, user_prompt)`. A
rewrite shares its step's system prompt, and the outline and draft rewrites carry the
brief too.

- The system prompt carries what the model is expected to do, then who it's doing it as:
  the persona fields the step chooses, plus tone and target audience.
- Each prompt class picks which persona fields it uses and where they go, so a later
  step such as a persona voice check can put them in the user prompt instead. The base
  class offers a helper that formats whichever fields a subclass asks for, so the
  formatting isn't repeated.
- The node service takes a step's prompt object in place of the two prompt lambdas.

**Run record.** `pb_generate_text_run` drops `persona_info` and gains `persona_id`
(FK to `pb_persona`, nullable only for runs made before this step), `tone` and
`target_audience`. No persona snapshot: `pb_llm_call` already stores every system and
user prompt as sent. Persona revisions are a later concern.

**Rules.** `fastapi-structure.md` › Prompts and the `Prompt` row in `python-naming.md`
change to one class per step extending `Base<Domain>Prompt`, returning a
`BuildPromptResult`.

## Step 2b — Persona CRUD frontend

Persona management for the signed-in user: list, view, create, edit, delete. Writing a
post from a persona comes later. So does the post-writing flow, including what the
nav's **Create** button does, which stays disabled until then.

**Nav:** **My Personas** (`/personas`) replaces the disabled **Write** item. A writing
shortcut may come back once posts exist.

**Routes**, all behind `RequireAuth`:

| Path                              | Page                                                                            |
| --------------------------------- | ------------------------------------------------------------------------------- |
| `/personas`                       | Your personas as cards, a **New persona** button, and an empty state            |
| `/personas/new`                   | Create form                                                                     |
| `/personas/:personaIdentity`      | Read-only profile with **Edit** and **Delete**. Later, "Write a post" goes here |
| `/personas/:personaIdentity/edit` | The same form, prefilled                                                        |

**Form:** one shared form component (`persona-form.tsx`) that create and edit both
render, in three sections:

- **Profile:** name, bio, avatar URL, public toggle
- **Voice:** background, writing style, sample writing
- **Defaults:** tone and audience

Every field has a short description with an example, and none offers suggestions to
click. Name and bio are required. Blank optional fields are sent as `null`. A 409 on
the name shows under the Name field. Built on TanStack Form and Zod: see
`react-structure.md` › Forms.

**Avatar:** a plain image URL for now, with an initial as the fallback. Step 6
replaces it with an upload.

**Delete:** a confirmation dialog on the profile page. On success, a toast and back to
the list.

**Toasts:** `sonner` — see `react-structure.md` › Toasts.

**Backend validation** added with this step. `PersonaDto` strips whitespace from name
and bio and requires both to be non-empty. Lengths:

| Field                                 | Limit                      |
| ------------------------------------- | -------------------------- |
| name                                  | 80                         |
| bio                                   | 500                        |
| background, writing_style             | 2000                       |
| default_tone, default_target_audience | 200                        |
| sample_writing                        | 10000                      |
| avatar_url                            | 2048, must be `http(s)://` |

The form's Zod schema mirrors these limits.

Open: the persona response doesn't say whether the caller owns it. Nothing needs that
until other users' public personas can be browsed, which is when Edit has to be hidden.

## Step 3a — Markdown blog post output

Every step that writes the post body (draft, draft rewrite, humanize, humanize rewrite)
writes Markdown, which is checked in code, never by another LLM call. The outline is a
plan, not the post, so it's left alone.

**Format.** A single `# Title` first, then `##` and `###` headings, paragraphs, bold
and italic, lists, blockquotes, links and code. No raw HTML, no images for now. The
rules text lives beside the check, in `graphs/blog_post/`, and the draft and humanize
system templates use it, so the instructions and the check can't drift apart.

**Output formats.** `BaseGenerateTextOutputFormat` has `normalize_output(output_text)`
and `validate_output(output_text) -> ValidateOutputResult(error_messages)`.
`BlogPostBodyOutputFormat` implements both:

- **Normalize** fixes only what can't change the meaning: a single fence wrapping the
  whole output, and surrounding whitespace. Never a preamble line.
- **Validate** checks: one leading `# Title`, no preamble, no raw HTML, no images,
  headings that don't skip levels.

The parsing is `markdown-it-py` (new dependency), behind `MarkdownUtils` in
`libs/core/utils/`, which the blog post service reuses in 3b to read the title.

**Nodes.** The generate and rewrite node builders take an optional `output_format`.
After the LLM returns, the node normalizes, then validates. On errors it retries once
with the same system prompt and the problems added to the user prompt; a second
failure raises `GenerateTextOutputInvalidException` (a 503, like a provider failure)
and the run fails. The retry count
is a `GenerateTextSettings` setting, default 1. The state stores the normalized text;
`pb_llm_call.response_text` keeps the raw response.

**Rules.** `python-naming.md` gains an `OutputFormat` suffix row, and
`fastapi-structure.md` › LangGraph workflows describes output formats.

## Step 3b — Content items and blog post CRUD

Two tables, one router per content type. `content_item` holds only what's true of any
content; the writing lives on the type's table.

**`pb_content_item`**, on top of `BaseOrm` (owner is `created_by_id`):

| Column         | Type                                 | Notes                                                   |
| -------------- | ------------------------------------ | ------------------------------------------------------- |
| `persona_id`   | BIGINT, NOT NULL, FK `pb_persona`    | Must be the caller's own persona                        |
| `content_type` | enum `pb_content_type` (`BLOG_POST`) | Its own enum, not `pb_text_type`                        |
| `is_public`    | bool, default false                  | Only allowed when the persona is public                 |
| `published_at` | timestamp, nullable                  | Null is a draft; past is published; future is scheduled |

**`pb_blog_post`**:

| Column            | Type                                                             | Notes                                    |
| ----------------- | ---------------------------------------------------------------- | ---------------------------------------- |
| `content_item_id` | BIGINT, NOT NULL, UNIQUE, FK `pb_content_item` ON DELETE CASCADE | Exists only as part of its content item  |
| `title`           | text, required                                                   |                                          |
| `subtitle`        | text, nullable                                                   |                                          |
| `body`            | text, required                                                   | Markdown, without the title and subtitle |

**`pb_generate_text_run`** gains `content_item_id` (nullable FK, indexed). The run
points at the content item because one post will be shaped by several runs over time.

**Services.** `ContentItemService` (`libs/content_items/`) owns the content item row:
create, access, visibility, publishing, soft delete. `BlogPostService`
(`libs/blog_posts/`) owns the blog post row and takes `ContentItemService` through
`__init__`. The `/blog-posts` router calls only `BlogPostService`. A cross-type feed
later gets its own `content_items` router.

**Routes.** `GET /blog-posts` lists the caller's own posts, newest first, filtered by an
optional `persona_identity` through `BlogPostFetchAllQueryDto` (no pagination yet).
`GET /blog-posts/{identity}`, `POST`, `PUT` (full replacement), `DELETE` (soft deletes
both rows). A post's persona never changes after create.

**Publishing.** `published_at` is in the create/update DTO. Publish now sends the
current time, schedule sends a future one, unpublish sends null. Reads compare it to
now, so a scheduled post appears when its time passes with no job.

**Saving from a run.** Its own route, `POST /blog-posts/from-generate-text-run`, taking
only `generate_text_run_identity`, `is_public` and `published_at`. The run must be the
caller's, finished, and not already saved (409). The server reads the run's final text,
splits it with `MarkdownUtils.split_post()` into title, subtitle and body, takes the
persona from the run, and links the run. Output that isn't in the post format (such as
a run from before Step 3a) is a 422. The plain `POST /blog-posts` is for posts written
by hand and takes no run. The frontend never splits Markdown.

**Body checks.** The create and update DTOs check the body with
`BlogPostValidationUtils`: no H1, only `##`/`###` without skipped levels, no raw HTML,
no images (a 422 naming the `body` field). The frontend's editor
writes Markdown and offers only what the format allows, so users never see Markdown.

**Visibility.** A validation guard rejects `is_public` on a private persona's content.
Reads compute it: others see a post only when it's public, published
(`published_at <= now`), and its persona is public, so a persona turning private hides
its posts without a cascading write. A public post on a private persona is a 422.

**Deferred.** Revising a post with a generate-text run: the run starts already pointing
at the content item, with the current post in its prompt, and on approval writes back
through the update or an "apply run" action. `pb_generate_text_run.content_item_id`
isn't unique, so a content item can already have many runs; only creating a post
from a finished run is limited to one link.

## Step 4 — Blog post CRUD frontend

Write a post with a persona, review each step, save the result, then manage your
posts: list, read, publish, edit and delete. Everything uses the routes from Steps 2a
and 3b, plus one backend change: the run response returns the run's inputs.

**Nav:** **My Posts** (`/posts`) joins **My Personas**. The **Create** button is
enabled and goes to `/write`.

**Routes**, all behind `RequireAuth`:

| Path                            | Page                                                          |
| ------------------------------- | ------------------------------------------------------------- |
| `/write`                        | The generate form. `?persona=<identity>` preselects a persona |
| `/write/runs/:runIdentity`      | One run: review a step, or save the finished post             |
| `/posts`                        | Your posts as cards, filtered by persona, with an empty state |
| `/posts/:blogPostIdentity`      | The rendered post with **Edit**, **Delete** and publishing    |
| `/posts/:blogPostIdentity/edit` | Title, subtitle, visibility and publish time                  |

The persona profile gains **Write a post** (to `/write?persona=...`) and a list of that
persona's posts.

**Generate form** (`POST /generate-text/blog-post`):

- **Persona:** a select of your personas. Choosing one prefills tone and audience from
  its defaults, which stay editable
- **Prompt** (required), **tone**, **target audience**, **additional context**
- **Steps:** outline, draft and humanize, each with an **on** switch and an
  **auto-approve** switch, all visible. Draft always runs, so it has no on switch.
  Defaults: every step on, none auto-approved

The call blocks until the run pauses for review or finishes, which can take a minute or
more, so the button shows a working state the whole time. On return, go to the run page.
If the call fails, the run is marked failed and the route returns an error, not a run,
so the page stays on the form with everything still filled in and shows the error.

`/write?from_run=<identity>` prefills the whole form, persona and step switches
included, from a run's inputs.

**Run page** (`GET /generate-text/runs/:runIdentity`), by `status`:

- **`AWAITING_REVIEW`:** the step's name and its output rendered as Markdown, then
  **Approve** or **Request changes** with a feedback box (`POST .../resume`). A step is
  rewritten at most `max_rewrite_passes` times; after that the run moves on
- **`COMPLETED`:** a preview of the post and **Save as post**
  (`POST /blog-posts/from-generate-text-run`) with the publishing controls below, then
  go to the post. A 409 means it's already saved
- **`FAILED`:** a short failure message and **Try again**, which opens
  `/write?from_run=...`. A resume that fails while you're on the page lands here too.
  The stored `error_message` is raw exception text, so it isn't shown
- **`RUNNING` / `PENDING`:** a working state that refetches

Run usage (tokens, cost) shows in a small footer. Runs aren't listed anywhere: there's
no route for it yet, so the URL is the only way back to an unfinished run.

**Run inputs on the run response.** `pb_generate_text_run` already stores every input,
so the server stays the source of truth rather than the browser remembering them.
`GenerateTextRunResponseDto` gains `persona_identity`, `prompt_text`, `tone`,
`target_audience`, `additional_context` and `options`, in the same shape the request
sent them. The run page also shows them as a "What you asked for" summary.

**Publishing controls**, shared by save and edit: **Public** switch (disabled with an
explanation when the persona is private), and **Draft**, **Publish now** or
**Schedule**. Schedule shows a date and time input; the time is sent with its offset,
because the backend refuses a naive one. Badges read the state from `published_at`:
null is Draft, future is Scheduled, past is Published.

**Rendering:** the post body is Markdown in the post format (Step 3a), rendered with
`react-markdown` (new dependency) and styles mapped to our tokens, with no typography
plugin. The title and subtitle come from their own fields.

**Not in this step:**

- **Editing the body.** It needs an editor that offers only what the format allows,
  so users never see Markdown. Until then, a post's body changes only by regenerating
- **Writing a post by hand** (`POST /blog-posts`), which lands with that editor
- **A list of runs** and run progress while a step is running

**Open:** a blog post response carries `persona_identity` but not the persona's name or
avatar, so the list joins against your personas query. When other users' public posts
can be browsed, the response should carry the persona summary instead.

## Step 5 — Background runs and polling

Generation stops being tied to an HTTP request. The request only starts a run, the run
works in the background, and the frontend polls until it finishes or pauses. Today
`POST /generate-text/blog-post` and `.../resume` hold the request open until the graph
pauses or ends, which can run past a proxy's idle timeout.

Human review is just another status: the run stops at `AWAITING_REVIEW`, the user
reviews, and `POST /generate-text/runs/{run_identity}/resume` continues it from the
saved checkpoint. A closed tab no longer matters; the run finishes and the user comes
back to it.

**Names here.** The source to-do used generic names. This plan maps them onto what
exists: the run is `pb_generate_text_run`, `queued` is `PENDING`, `paused` is
`AWAITING_REVIEW`, and the routes stay under `/generate-text`. Items already true of
the code are ticked.

### Phase 1: The 60s cutoff, and the models

The cutoff seen so far is most likely the LLM call's own timeout, not the HTTP layer:
the STRONG tier's `request_timeout_seconds` is 60, and it only failed on the expensive
STRONG model. Background runs remove the HTTP side of the risk; this fixes the LLM side.

- [x] The frontend client sets no global timeout: `apiClient` (`openapi-fetch`) has none
- [ ] Confirm it from `pb_llm_call`: the failed STRONG calls carry a timeout
  `error_code` and a `duration_ms` near 60000
- [x] Raise STRONG's `request_timeout_seconds` to 120
- [x] Don't retry a timed-out call. The OpenAI SDK retries timeouts as part of
  `max_retries`, so turn its retries off and retry 429s and 5xx errors ourselves, with
  backoff and jitter
- [x] Move FAST off `gpt-4o-mini` (the 4o family is being retired) to `gpt-5.4-nano`
  ($0.20 / $1.25 per 1M tokens), and add its price to `model_pricing`
- [ ] Check STRONG's `gpt-5.6-sol` price in `model_pricing` ($4 / $20) against
  OpenAI's page: sources list it at $5 / $30, with $4 / $20 as a promotion
- [x] GPT-5 models are reasoning models, and `max_output_tokens` includes their
  reasoning tokens, so FAST's 2048 can run out before any outline is written. Raise it,
  or send a low `reasoning.effort` per tier

### Phase 2: Run model and endpoints

The database row is the source of truth for every run; endpoints only start, read and
steer it.

**`pb_generate_text_run` already holds most of it:**

| Need                          | Where it is                                              |
| ----------------------------- | -------------------------------------------------------- |
| Run ID and LangGraph thread   | `identity`, already the `thread_id`                      |
| Who and with what             | `created_by_id`, `persona_id`, `prompt_text`, `tone`, `target_audience`, `additional_context`, `options` |
| Status                        | `status`: `PENDING`, `RUNNING`, `AWAITING_REVIEW`, `COMPLETED`, `FAILED`, `CANCELLED` |
| Steps for the progress UI     | `pb_generate_text_step` rows, one per node attempt       |
| Output                        | The latest step's output, and `content_item_id` once saved as a post |
| Error                         | `error_code`, `error_message`                            |
| Heartbeat                     | A lease for running runs (see Deploys and restarts)     |

**Decided:**

- No idempotency key. A resume already answers 409 unless the run is paused, so a
  repeated resume can't run twice. A repeated start is a double click, which the
  disabled button stops; if that ever isn't enough, the client can send the run's
  identity, which already exists, rather than a new column
- No `current_step` column. A step row is written as `RUNNING` when its node starts, so
  the newest step row is the current step, and a second copy could drift from it

- No cancel for now. A paused run costs nothing while it waits, and a running one
  finishes in about a minute. Revisit with the usage plans (6c)

**Endpoints:**

- [x] `POST /generate-text/blog-post`: insert the row, start the background run, return
  `202 Accepted` with the run
- [x] `GET /generate-text/runs/{run_identity}`: returns status, the last step and its
  output, and checks the run belongs to the caller
- [ ] `GET /generate-text/runs/{run_identity}` also returns the list of steps for the
  progress UI
- [x] `POST /generate-text/runs/{run_identity}/resume`: takes the review decision, sets
  `RUNNING`, continues from the checkpoint in the background, and returns `202`

### Phase 3: Background execution and LangGraph async audit

The run only stays cheap and non-blocking if every step in it is async, end to end.

**Running the work in the background:**

- [x] Start the run as a background job with `BackgroundJobService.start()`, which runs
  it with `asyncio.create_task` in the API process and holds a reference until it's
  done. Python can garbage-collect a task nobody references
- [x] Wrap the run body in `try` / `except`: set `FAILED` and the error on any
  exception. For now a job cancelled at shutdown is marked `FAILED` (`ServerShutdown`);
  the lease PR hands it off instead (see Deploys and restarts)
- [ ] Run the graph with `astream(..., stream_mode="updates")` instead of `ainvoke`,
  so the task can stop cleanly between nodes. LangGraph saves a checkpoint after every
  node

### Deploys and restarts

A follow-up PR, after polling lands.

**Decided for the lease PR:**

- **Created leased.** A run is inserted with its creator's lease, so the pickup loop never
  takes a run whose job is about to start. A run claimed for resume takes the lease in
  the same update. Pausing, completing or failing clears it.
- **Stop between steps.** On shutdown, each job finishes the step it's on, LLM call
  included, then stops before the next one and releases the run. The drain deadline
  (`BACKGROUND_JOBS__SHUTDOWN_DRAIN_SECONDS`) rises from 30 to 150, above STRONG's 120s
  timeout, so a step always has time to finish.
- **Deadline as a safety net.** A job still running at the deadline (something hung) is
  cancelled and its run released, not failed. Another instance redoes that step from
  the last checkpoint.
- **Orphaned start.** A `PENDING` run whose lease expires never started, so it has no
  checkpoint to resume from. The pickup loop marks it `FAILED`; the run page offers Try
  again.
- **A lost resume.** If a process dies after claiming a resume but before the graph
  takes the decision, the checkpoint is still at the interrupt. The picked-up run pauses
  for review again; the decision is already saved on the step, and the user approves
  again.
- **Timings,** as `GenerateTextSettings`: lease 60s, heartbeat 15s, pickup every 30s,
  and a run picked up more than 3 times is marked `FAILED`.
- **Instant handoff** stays the next PR. Until then, a released run waits for the next
  pickup, up to 30s.

**Decided for the handoff PR:**

- **A Redis list, not a stream.** The stopping process `RPUSH`es the run id once its
  release has saved, and each live process waits on `BLPOP`. Each message reaches one
  listener, and messages wait in the list when nobody is listening.
- **The message is only a wake-up.** A listener that receives one runs one pickup,
  which claims whichever run expired longest ago. The database claim stays the lock.
- **No acknowledgements.** A message is lost if Redis is down when it's sent, or if a
  listener dies between taking it and saving its claim, a few milliseconds. The 30s
  pickup loop stays and catches both. A stream with a consumer group (`XREADGROUP`,
  `XACK`, `XAUTOCLAIM`) would recover the second case on the same 30s schedule, so its
  guarantees would only duplicate the run row's lease and `pickup_count`.
- **Revisit with a proper queue** if generation moves out of the API into a worker
  app. The queue message would then start the run and be the only record of it, so it
  needs acknowledgements and redelivery.
- **Only a released run is handed off:** one stopped between steps at shutdown, or
  cancelled at the drain deadline while still holding its lease. A paused, finished or
  failed run, a lease lost to another process, and a crashed process send nothing.
- **The database clock** sets a released lease's expiry and judges whether a lease has
  expired, so a listener whose clock runs behind the releaser's still sees the run as
  expired.

A run can take minutes, longer than any deploy should wait. So a stopping process
finishes the node it's on, saves, and hands the rest of the run to a live process.
No run is lost, and at most one node is redone.

**What happens on a Railway deploy:**

1. The new deployment starts and passes its healthcheck (`/health`)
2. Traffic moves to it. The old one keeps running for `overlapSeconds`; one report
   says requests can still reach the old one during that window, so test it
3. The old one gets `SIGTERM`, then `SIGKILL` after `drainingSeconds`. The default may
   be 0, an immediate kill, so set it explicitly
4. On `SIGTERM`, granian stops accepting connections, finishes in-flight HTTP requests,
   then runs each worker's lifespan shutdown. Background jobs are invisible to it:
   draining them is the app's job

**The app's side:**

- [ ] **Ownership.** Only a `RUNNING` run has a lease: `lease_owner` (the worker
  process: Railway's replica ID or the hostname, the PID and a random suffix) and
  `lease_expires_at` (60s), renewed by a heartbeat every 15s. A paused, completed or
  failed run has none, so a resume can land on any instance: it claims the lease in
  the same `UPDATE … WHERE status = 'AWAITING_REVIEW'` that sets `RUNNING`, which also
  turns a second resume into a 409
- [ ] **Owner check.** The heartbeat renews with `WHERE lease_owner = me`. If that
  changes no rows, another instance has taken the run, so the task stops instead of
  running alongside it
- [ ] **Graceful stop.** Lifespan shutdown sets a stop flag. Each run task finishes the
  node it's on (bounded by STRONG's 120s timeout), stops before the next one, and
  releases its lease (`lease_expires_at = now()`). The run stays `RUNNING`
- [x] **Bounded wait.** Shutdown waits for the jobs with a deadline shorter than
  `drainingSeconds`, then cancels what's left. A cancelled job's node is lost, but
  its last checkpoint isn't
- [ ] **Pick-up.** A pickup loop, on startup and every ~30s, claims `RUNNING` runs whose
  lease has expired (`FOR UPDATE SKIP LOCKED`, so two workers or replicas never claim
  the same run) and resumes each from its checkpoint (`ainvoke(None, config)`). This
  also covers a crash or a `SIGKILL`: the lease runs out and another process picks the
  run up
- [ ] **Paused runs need nothing.** An `AWAITING_REVIEW` run has no task; its state is
  in the database and the Redis checkpoint, so a resume can land on any worker
- [ ] A run whose resume keeps failing after a few pick-ups is marked `FAILED`, so a
  poisoned run can't loop forever
- [ ] **Instant handoff** (a follow-up after the lease PR). A stopping process that
  releases a run mid-way pushes its id onto a Redis list. Each live worker waits
  on that list (`BLPOP`) and claims the run at once, so the user doesn't wait for the
  next pickup. The database claim stays the lock and the pickup loop stays the backup: a
  duplicate or stale message claims nothing. A stopping worker stops reading the list
  before it releases its own runs
- [x] **Comment cleanup** (the PR after instant handoff). Bring existing backend and
  frontend code in line with the comment rules: one-sentence docstrings, and a short
  comment above each block of a multi-step function
- [x] **Public docstrings** (the PR after comment cleanup). Every public function,
  method and class gets a one-sentence docstring saying what its name doesn't: what it
  returns in an edge case, raises, writes or starts. Turn on ruff's `D1` rules to
  enforce it, exempting tests, `dtos.py`, `results.py`, `inputs.py`, `settings.py`,
  `types.py` and `__init__.py`. Private helpers get one only when the name isn't
  enough. Update `python-naming.md` › Other conventions to match
- [x] **Writes as statements.** Switch Orm writes from setting attributes and calling
  `flush()` to one statement that sets every field, so a time it writes is
  `DatabaseClockUtils.build_utc_now_sql()` rather than the app server's clock. Updates
  become one `update()` statement, and creates become one `insert()` statement the
  same way, instead of `add()` and `flush()`. Rewrites `fastapi-structure.md` › Querying
  and writing. Clears every `TODO(db-clock)`, including the two inserts
  (`create_run`'s lease expiry, `create_step`'s `started_at`), and removes `BaseOrm`'s
  `eager_defaults`, which only matters while records are flushed

**Railway and granian settings:**

- [ ] `healthcheckPath = "/health"`, `overlapSeconds` short (~10s), `drainingSeconds`
  above the app's drain deadline (for example a 150s deadline and 180s draining), set
  in Railway's config-as-code file
- [ ] Start granian directly (exec form in the Dockerfile, or `exec` in a script), so
  it's PID 1 and gets `SIGTERM`. A wrapper like a shell script swallows it
- [ ] Leave `--workers-lifetime` and `--workers-max-rss` off at first: each recycles a
  worker, which stops its runs. The handoff makes it safe, but there's no need for it
- [ ] `--workers-kill-timeout` above the drain deadline, so granian only kills a worker
  that hangs past it

**Confirm the graph is fully async:**

- [x] The graph runs with `await graph.ainvoke(...)`
- [x] Every node is an `async def`
- [x] LLM calls inside nodes use the async client (`AsyncOpenAI`)
- [x] DB access inside nodes uses the async session; no sync `requests`, file I/O or
  `time.sleep` anywhere in `libs/` or `apps/`
- [x] Checkpointer: keep `AsyncRedisSaver`. It already works across workers; Railway's
  Redis needs persistence on, so a restart doesn't drop paused runs
- [x] `config = {"configurable": {"thread_id": ...}}` uses the run's identity, so the
  checkpoint and the run row share an ID
- [x] Human review uses LangGraph's `interrupt()`, and resume calls the graph again with
  `Command(resume=...)` and the same `thread_id`

**Prove it doesn't block:**

- [ ] During a running generation, hit `/health` repeatedly; it should answer in
  milliseconds
- [ ] Run locally with `PYTHONASYNCIODEBUG=1`; asyncio logs any step that holds the loop
  for more than 100ms
- [x] An event loop lag monitor, started in `lifespan` in development: a task that
  sleeps a fixed interval, measures how late it wakes, and logs any delay over a
  threshold. Leave it running during a long real generation

### Phase 4: LLM call hygiene

Treat every LLM call as a slow, flaky, rate-limited dependency that costs money.

- [x] A timeout on every call: each tier's `request_timeout_seconds`
- [x] Retries with backoff and jitter on 429s and 5xx errors, done by us, not the SDK,
  so timeouts and 4xx input errors are never retried (Phase 1)
- [ ] A shared `asyncio.Semaphore` capping concurrent calls per worker, sized to the
  provider's rate limits
- [x] Tokens and cost recorded per call (`pb_llm_call`), per step and per run
- [x] Provider request IDs are stored on each call (`provider_request_reference`)

### Phase 5: Frontend polling

The frontend starts a run once, then only reads it, so a refresh, a closed tab or a
dropped connection costs nothing.

- [x] **Write post** goes straight to
  `/write/runs/:runIdentity` instead of waiting on the request
- [x] Poll `GET /generate-text/runs/{run_identity}` while the status is `PENDING` or
  `RUNNING` (React Query's `refetchInterval`, which also handles cleanup)
- [x] Poll at the interval the run response gives: a backend setting,
  `GENERATE_TEXT__POLL_INTERVAL_MS`, 2000 by default, so it can change per deploy
  without rebuilding the frontend
- [x] Stop polling on `COMPLETED`, `FAILED`, `CANCELLED` or `AWAITING_REVIEW`
- [x] Show progress from the steps ("Outlining…", "Drafting…") in the step tracker
- [x] `AWAITING_REVIEW` shows the review UI; submitting calls `/resume`, which returns at
  once, and polling restarts
- [x] Back off on errors (for example 3s, then 6s, then 12s) instead of hammering a
  failing API
- [x] On page load with a run identity in the URL, the run page reads that run and polls
  it

### Phase 6: Deploy readiness on Railway

Assume any worker can restart mid-run and any request can land on any replica.

- [ ] Granian `--workers` read from an env var (start with 2; raise toward the vCPU count
  if CPU nears one core)
- [ ] No in-memory state that matters: runs, checkpoints and progress all live in
  Postgres or Redis
- [ ] A `/health` endpoint set as Railway's healthcheck, so new deploys only take traffic
  once ready (`/health` exists)
- [ ] The handoff in Deploys and restarts covers runs a redeploy stops
- [ ] Size the database connection pool for workers × replicas, so it stays under
  Postgres's connection limit
- [ ] Secrets (API keys, the database URL) only in Railway variables

### Later

Worth doing once the core flow works; none of it changes the API shape above. Some of
it overlaps Steps 8, 9 and 10.

- [ ] **Generation worker.** Move runs to a job queue with a separate worker app
  (`apps/worker/`), so API deploys never touch running work. A job is one segment of a
  run: start or resume, then run the graph until it pauses for review or ends, then
  acknowledge. The queue's guarantees replace the lease machinery: delivery to one
  worker replaces the claim, the acknowledgement deadline replaces the lease expiry,
  extending it replaces the heartbeat, redelivery of unacknowledged jobs replaces the
  pickup loop and the handoff list, and the delivery count replaces `pickup_count`.
  Still needed: a guard against a redelivered job running beside a slow original, and
  a deadline longer than a step. Compare `arq` (asyncio, on our Redis, with cron) and
  Taskiq, including how each treats a worker that dies mid-job
- [ ] An optional SSE progress stream, `GET /generate-text/runs/{run_identity}/events`
  (heartbeats, a final `done` event, `Last-Event-ID`), with polling as the fallback
- [ ] Structured logs carrying the request ID and run ID on every line (Step 8)
- [ ] Metrics: run duration per step, LLM latency, tokens, failure rate, runs in
  progress (Step 9)
- [ ] A per-user rate limit on starting runs, and input size limits
- [ ] Per-user token or cost quotas (with the usage plans in 6c)

**Decided:** the graph runs in the API process with `asyncio.create_task`; a job queue
can come later (see Later). STRONG's timeout is 120s, and timeouts aren't retried.

**Open questions:**

- Lease columns (`lease_owner`, `lease_expires_at`), or `updated_at` staleness as the
  lease
- Railway's `overlapSeconds` and `drainingSeconds`, and whether requests reach the old
  deployment during overlap. Settle both when deploying (Step 10)
