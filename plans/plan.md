# Persona Blog — build plan

The outline from here on. Detail gets added to each step as it comes up.

1. **Persona CRUD — backend**
2. In parallel:
   - **Persona in generate text** — pass a persona into the generate text call and
     its prompts
   - **Persona CRUD — frontend**
3. **Avatar upload** — replaces the avatar URL field with a real upload:
   - **Backend:** store images in S3 and add an upload route that returns the stored
     image's URL
   - **Frontend:** the persona form uploads the chosen image, then sends the returned
     URL as `avatar_url` on create or update
4. **Blog post CRUD — backend.** Open question: a generic `content_items` table with
   `blog_post` beside it, or just `blog_post`. Writing gets its own `is_public` too: a
   public persona can have public or private posts, a private persona only private ones
5. **Blog post CRUD — frontend**
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

Every field is open text. The frontend (step 2) shows a description with an example for
each field.

Routes under `/personas`: create, list the caller's own, get, update, soft delete.

Access:

- **Read** — your own persona, or anyone's public one. Someone else's private persona
  is a 404, so its existence doesn't leak.
- **Update, delete** — the creator only. Someone else's public persona is a 403; their
  private one is still a 404.
- **List** — your own only, returned as `{"personas": [...]}`. No pagination yet.
  Browsing other users' public personas waits for persona search.

## Step 2 — Persona CRUD frontend

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

**Avatar:** a plain image URL for now, with an initial as the fallback. Step 3
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
