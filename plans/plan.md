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
5. **Avatar upload** — replaces the avatar URL field with a real upload:
   - **Backend:** store images in S3 and add an upload route that returns the stored
     image's URL
   - **Frontend:** the persona form uploads the chosen image, then sends the returned
     URL as `avatar_url` on create or update
6. **Testing and fine tuning** — try adding or removing steps in the generate text
   process, different models, different prompts
7. **Logging** — proper logging for the endpoints and for the graph
8. **Log tracking service** — set it up and test it

## Step 1 — Persona CRUD backend

Table `pb_persona`, on top of `BaseOrm`'s columns. The owner is `created_by_id`, the
same as `pb_generate_text_run`, so there's no separate `user_id`.

| Column                    | Type           | Notes                                                    |
| ------------------------- | -------------- | -------------------------------------------------------- |
| `name`                    | text, required | Pen name; unique per owner among live rows               |
| `bio`                     | text, required | Short public summary                                     |
| `avatar_url`              | text, nullable |                                                          |
| `background`              | text, nullable | Backstory that shapes their view                         |
| `expertise`               | text, nullable | What they know and write about                           |
| `writing_style`           | text, nullable | Sentence length, vocabulary, formatting habits           |
| `default_tone`            | text, nullable | Prefills tone when asking the persona to write something |
| `default_target_audience` | text, nullable | Prefills audience the same way                           |
| `sample_writing`          | text, nullable | A passage in their voice for the model to imitate        |
| `is_public`               | bool, default false | Others can read the profile; later, persona search  |

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

| Field              | Type             | Notes                                                  |
| ------------------ | ---------------- | ------------------------------------------------------ |
| `persona_identity` | UUID, required   | One of the caller's own personas; anyone else's is 404 |
| `tone`             | text, nullable   | The frontend prefills it from `default_tone`           |
| `target_audience`  | text, nullable   | Prefilled from `default_target_audience`               |

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

| Path                              | Page                                                   |
| --------------------------------- | ------------------------------------------------------ |
| `/personas`                       | Your personas as cards, a **New persona** button, and an empty state |
| `/personas/new`                   | Create form                                            |
| `/personas/:personaIdentity`      | Read-only profile with **Edit** and **Delete**. Later, "Write a post" goes here |
| `/personas/:personaIdentity/edit` | The same form, prefilled                               |

**Form:** one shared form component (`persona-form.tsx`) that create and edit both
render, in three sections:

- **Profile:** name, bio, avatar URL, public toggle
- **Voice:** background, expertise, writing style, sample writing
- **Defaults:** tone and audience

Every field has a short description with an example, and none offers suggestions to
click. Name and bio are required. Blank optional fields are sent as `null`. A 409 on
the name shows under the Name field. Built on TanStack Form and Zod: see
`react-structure.md` › Forms.

**Avatar:** a plain image URL for now, with an initial as the fallback. Step 5
replaces it with an upload.

**Delete:** a confirmation dialog on the profile page. On success, a toast and back to
the list.

**Toasts:** `sonner` — see `react-structure.md` › Toasts.

**Backend validation** added with this step. `PersonaDto` strips whitespace from name
and bio and requires both to be non-empty. Lengths:

| Field                                     | Limit                        |
| ----------------------------------------- | ---------------------------- |
| name                                      | 80                           |
| bio                                       | 500                          |
| background, expertise, writing_style      | 2000                         |
| default_tone, default_target_audience     | 200                          |
| sample_writing                            | 10000                        |
| avatar_url                                | 2048, must be `http(s)://`   |

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

| Column         | Type                               | Notes                                  |
| -------------- | ---------------------------------- | -------------------------------------- |
| `persona_id`   | BIGINT, NOT NULL, FK `pb_persona`  | Must be the caller's own persona       |
| `content_type` | enum `pb_content_type` (`BLOG_POST`) | Its own enum, not `pb_text_type`     |
| `is_public`    | bool, default false                | Only allowed when the persona is public |
| `published_at` | timestamp, nullable                | Null is a draft; past is published; future is scheduled |

**`pb_blog_post`**:

| Column            | Type                                                       | Notes    |
| ----------------- | ---------------------------------------------------------- | -------- |
| `content_item_id` | BIGINT, NOT NULL, UNIQUE, FK `pb_content_item` ON DELETE CASCADE | Exists only as part of its content item |
| `title`           | text, required                                             |          |
| `subtitle`        | text, nullable                                             |          |
| `body`            | text, required                                             | Markdown, without the title and subtitle |

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
