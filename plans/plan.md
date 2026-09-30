# Persona Blog — build plan

The outline from here on. Detail gets added to each step as it comes up.

1. **Persona CRUD — backend**
2. In parallel:
   - **Persona in generate text** — pass a persona into the generate text call and
     its prompts
   - **Persona CRUD — frontend**
3. **Blog post CRUD — backend.** Open question: a generic `content_items` table with
   `blog_post` beside it, or just `blog_post`. Writing gets its own `is_public` too: a
   public persona can have public or private posts, a private persona only private ones
4. **Blog post CRUD — frontend**
5. **Testing and fine tuning** — try adding or removing steps in the generate text
   process, different models, different prompts
6. **Logging** — proper logging for the endpoints and for the graph
7. **Log tracking service** — set it up and test it

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

Every field is open text. The frontend (step 2) offers suggested values for tone and
audience, and the user can still type their own.

Routes under `/personas`: create, list the caller's own, get, update, soft delete.

Access:

- **Read** — your own persona, or anyone's public one. Someone else's private persona
  is a 404, so its existence doesn't leak.
- **Update, delete** — the creator only. Someone else's public persona is a 403; their
  private one is still a 404.
- **List** — your own only, returned as `{"personas": [...]}`. No pagination yet.
  Browsing other users' public personas waits for persona search.
