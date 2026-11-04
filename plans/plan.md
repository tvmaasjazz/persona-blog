# Persona Blog — plan

The plan from here on, in three phases: get to an initial deploy, then harden the app
(security, idempotency, visibility), then add features. Detail gets added to each item
as it comes up. What was built before this plan, and how it was designed, is in
[`archive/build-plan-v1.md`](archive/build-plan-v1.md).

Each item lists the decisions it still needs. They're made when the item comes up, not
before.

## Phase 1 — Initial deploy

### 1. Roles, permissions and credits

What a user may do comes from their role's permissions. What a creator may spend comes
from their credit balance. There are no payments yet, but both are the shapes payments
will use. The backend is done: roles and permissions in #36, credits in #37. The
frontend comes in item 6.

**Roles:**

- **Admin:** every permission, and charged like anyone. Tyler, and anyone added later.
- **Creator:** creates personas and blog posts, and generates, paid from their balance.
  For now the admin makes someone a creator and grants them credits; later a user
  becomes one by adding payment details and a first top-up.
- **Reader:** signs in only to read: other people's posts and comments, and later
  following a persona's blog for email notifications. Never posts. Every new user
  starts as a reader.
- **System:** the system user's role, with no permissions. The system user never
  signs in; a job may write as it.

**Permissions:**

- Permissions live in tables: a role table, a permission table and a join between them,
  and each user has exactly one role. No per-user grants: a user's permissions are
  their role's. Code checks permissions, never roles: a route lists the permissions it
  needs with `Depends(require_permissions(...))`, reads included, and a test fails any
  route that names none and isn't on its short list of open routes.
- Permissions: `PERSONA_READ`, `PERSONA_WRITE`, `BLOG_POST_READ`, `BLOG_POST_WRITE`,
  `GENERATE_TEXT_RUN_READ` and `GENERATE_TEXT_RUN_WRITE`. Admin and creator hold them
  all; a reader holds the persona and blog post reads; System holds none.
- The admin role holds every permission as explicit rows, not a wildcard, so each
  migration that adds a permission grants it to the admin.
- Existing users are backfilled as creators. The first admin is set with an SQL update
  in each environment, not a migration, so the admin's email stays out of the repo.
- A user's role and permissions are cached in their sign-in session, so the auth guard
  reads no table per request. A stored session that doesn't match the current shape is
  treated as expired, so a change to the session's shape costs one sign-in and no
  deploy step.
- Granting credits makes the user a creator: `backend/scripts/grant_credits.py` today,
  the admin panel (item 2) next. Anything else is SQL. Changing a role in code deletes
  the user's sessions, and they sign in again with the new set. A user has a session per
  browser or device, and sessions are in Redis by session id today, so the admin panel
  PR adds a per-user set of session ids to find them all. After an SQL change, the user
  signs out and in.

**Credits:**

- Balances are in USD, in the code, the database and the API.
- Each LLM call keeps its cost to us, `cost_usd`. Beside it, a step and its run get
  `charge_usd`, what the user pays, from one function. For now the function returns the
  cost unchanged; later it applies a markup.
- `pb_credit_ledger` records every change to a balance: the user, a signed USD amount,
  the kind (`GRANT` for free credits, `CHARGE`, `REFUND`, `ADJUSTMENT`, and `PURCHASE`
  with payments), the run and step it concerns, a note, and who made it. It's the source
  of truth, and a balance cached on the user is updated in the same transaction as each
  row. Grants and purchases stay apart, so revenue and giveaways can be counted
  separately.
- **Charged per step.** Each step that succeeds is charged its `charge_usd` in the same
  transaction that marks it done, in `complete_step()`. A step redone after a crash or a
  deploy is charged once, since only a succeeded step is charged. `libs/llm` knows
  nothing about credits.
- **A failed run refunds what the user hasn't seen.** A run moves in segments, each
  started by an endpoint call (start or resume) and ended by a pause for review,
  completion or failure. When a run fails, the charges for the steps after its latest
  review step are refunded, in the same transaction as `fail_run()`, which every failure
  path goes through. The boundary comes from the step rows, so a run picked up after a
  crash finds the same one.
- **Admins are charged like anyone.** There's no exempt permission; the admin grants
  themself credits.
- **Before a run starts or resumes,** the balance must be at least a minimum (a setting,
  $0.10), and the user must have fewer than the maximum active runs (`PENDING` or
  `RUNNING`; a setting, 2). Nothing is held, so a run that's already going can take the
  balance below zero, by at most about the active-run limit's worth of runs; a negative
  balance blocks the next run until it's topped up. No locking: two requests at the
  same instant could pass the active-run check together, which is harmless for now.
- Every model in a tier must have a price, checked when the settings load, so the app
  won't start with a model it would charge nothing for.
- Persona creation isn't limited; rate limiting (Phase 2) stops spam. Voice to form
  isn't charged: it's a feature of the site, and its cost is ours. Avatar generation
  is charged, added with avatars (Phase 3).
- **Below the minimum balance:** the run is refused with a 402 Payment Required, from a new
  standard `PaymentRequiredException` (402 isn't covered by any category yet), and the
  frontend shows that the balance is too low and must be topped up.
- **Low balance warning:** below a threshold (a setting, $0.50 to start) the user
  response says the balance is low, and the app shows a banner, so a creator knows
  they're running out before a run is refused. Granted credits get the same warning
  now; with payments, it shows only to users without auto-refill.

### 2. Admin panel (backend)

One PR. Admin-only endpoints for the admin panel's pages (item 6):

- **Users:** every user with their role and balance. No search or pagination yet; the
  list takes on item 5's after it lands.
- **Grant credits:** an amount and a note, written as a `GRANT` on the ledger. A reader
  becomes a creator, and their sessions are deleted so they sign in with the new role.
  This needs the per-user set of session ids (item 1 › Permissions).
  `backend/scripts/grant_credits.py` stays for granting without the panel.
- **A user's ledger:** their ledger rows, newest first.

**To decide:**

- The new permissions, held by the admin only: one read and one write (`USER_READ` and
  `USER_WRITE`, say), or one per action
- The route prefix, `/admin/...` or under each resource
- Whether the admin can also set a role directly, such as turning a creator back into a
  reader

### 3. Invite links (backend)

One PR. The admin creates an invite carrying a name, a credit amount, a note and an
expiry, and gets back its link. There's no email in the app: the admin copies the link
and sends it by email or text. The name is required and says who it's for, since the
invite isn't tied to an email, so the list shows who each link went to.

- The link holds a one-time code. Only its hash is stored, so the link is shown once,
  when it's created.
- The code is carried through Google sign-in in the OAuth state. Signing in with it,
  with any Google account, uses it up: the user becomes a creator and gets the credits
  as a `GRANT` on the ledger, with the invite on the row.
- The admin lists invites with their name and status (unused, used and by which account,
  expired) and can revoke an unused one.

**To decide:**

- What an invite does for someone who already has an account: the same upgrade and
  grant, or refused
- The default expiry

### 4. Post views and the feed's order (backend)

One PR. Simple counts of how posts are read, and a score to order the homepage by.

- **Views:** the frontend records a view when a post opens. One view per viewer, per
  post, per day: by user when signed in, else by an anonymous id in a cookie.
- **How far they read:** the frontend reports the furthest point read, in quarters (25,
  50, 75, 100%), as the reader scrolls, stored on the view.
- **The score:** recent engagement over age, as in Hacker News. Each view in the last 7
  days counts 1, plus 3 times the share of the post it read, so a half read adds 1.5 and
  a full read 3. Partial reads count for what they read:
  `(sum of (1 + 3 × read share) + 1) / (hours since publishing + 2) ^ 1.5`. The weights
  and the window are settings, so the order can be tuned without a deploy. It's
  computed in the query; with many posts, a cached score per post, refreshed on a
  schedule.
- Authors see their posts' views and how far they were read.

**To decide:**

- A view row per viewer per day, or counts per post per day, which lose who viewed but
  stay small
- Whether a view by the post's own author counts

### 5. Pagination, search and the homepage feed (backend)

One PR. One way of paging and searching every list in the app, used first by the
homepage feed. The admin's user list and the other lists take it on after.

- **Pagination:** a page size and a cursor or offset, and the same response shape on
  every list.
- **Search:** one search box per list, matching the fields that list chooses (a post's
  title and body, a user's email and name). Filters can be fixed by the page at first,
  with no filter menu yet.
- **The homepage feed:** every public post, ordered by the score (item 4), paged, with
  a search.
- **A persona's page:** a public persona's public posts, so anyone can read a persona
  and what it's written. Today's lists show only the signed-in user's own.
- **Reading signed out:** the feed, a persona, a persona's posts and a post are open
  routes, with no permission, so a shared link works for anyone. Sign-in is optional on
  them: a signed-in owner still sees their own private persona or post, and anyone else
  gets a 404 for one, as `find_persona` and `find_blog_post` do today. They join the
  open routes list in `test_app_factory.py`. Recording a view is open too. The owner's
  own lists, writes and generation keep their permissions.
- The frontend's table, search box and pager, built once in item 6 and used by every
  list.

**To decide:**

- Cursor or offset pagination. A cursor keeps pages steady while new posts arrive, but
  can't jump to a page number
- Search with Postgres full-text search, or a simple `ILIKE` to start
- Whether a public post of a private persona shows to others, or a post needs both
  public
- Whether the reads `PERSONA_READ` and `BLOG_POST_READ` still mean anything once these
  routes are open, or are folded into the owner's lists

### 6. Frontend

Everything the backend-only PRs added, before the deploy:

- **Roles:** a reader sees no create, edit or generate actions, and a 403 shows a
  message rather than an error.
- **Credits:** the balance on the profile, the low balance banner, and the 402 message
  when a run is refused.
- **Admin panel:** users with their role and balance, granting credits with a note, a
  user's ledger, and creating, listing and revoking invites, with the new link shown
  once to copy.
- **Invite sign-up:** the link's page signs the user in with Google, carrying the code,
  and says what they got.
- **Homepage:** the feed, replacing My personas as the start page, with search and
  paging, and recording views and how far a post is read.
- **A persona's page:** its public posts, reached from a post or the feed.
- The table, search box and pager the lists share.

Probably more than one PR, split by area: the shared pieces and roles and credits first,
then the admin panel and invites, then the homepage and persona pages.

### 7. Deploy readiness

Assume any worker can restart mid-run and any request can land on any replica. The
lease, handoff and drain work in the archive covers runs a redeploy stops.

- [ ] A Dockerfile for the backend that starts granian directly (exec form), so it's
  PID 1 and gets `SIGTERM`. A wrapper like a shell script swallows it
- [ ] Granian `--workers` read from an env var (start with 2; raise toward the vCPU
  count if CPU nears one core)
- [ ] `--workers-kill-timeout` above the 150s drain deadline, so granian only kills a
  worker that hangs past it. Leave `--workers-lifetime` and `--workers-max-rss` off:
  each recycles a worker, which stops its runs
- [ ] Railway's config-as-code file: `healthcheckPath = "/health"`, `overlapSeconds`
  short (~10s), `drainingSeconds` above the drain deadline (180s)
- [ ] Migrations run as a pre-deploy step, before the new version takes traffic
- [ ] Size the database connection pool for workers × replicas, so it stays under
  Postgres's connection limit
- [ ] Secrets (API keys, the database URL) only in Railway variables
- [ ] The frontend's production build pointed at the API's URL, the API's CORS allowing
  the frontend's origin, and Google sign-in's redirect URIs for the production domain
- [ ] During a running generation, hit `/health` repeatedly; it should answer in
  milliseconds
- [ ] Check STRONG's `gpt-5.6-sol` price in `model_pricing` ($4 / $20) against OpenAI's
  page: sources list it at $5 / $30, with $4 / $20 as a promotion

**To decide:**

- A subdomain of an existing domain first, or a dedicated domain from the start

### 8. Initial deploy

- [ ] Deploy the frontend, the backend, Postgres and Redis on Railway
- [ ] Run the `backend/scripts/e2e/` scripts against the deployed API
- [ ] Give Tyler's user the admin role, and grant it credits
- [ ] Send the first invite links

## Phase 2 — Security, idempotency and visibility

In the order they're listed, unless something on the live app moves one up.

### 1. Logging and tracking

- [ ] Structured logs carrying the request ID, and the run ID inside a run, on every line
- [ ] Metrics: run duration per step, LLM latency, tokens, failure rate, runs in progress
- [ ] Set up the log tracking service and check each of the above reaches it

**To decide:** what to track beyond the above, and the alerts worth having.

### 2. Idempotency keys

A repeated request, such as a double click on generate, returns the first request's
response instead of running twice.

- The frontend sends an `Idempotency-Key` header, a new UUID per user action, reused
  when that action is retried. Generate text first, then the create routes.
- The backend handles it for the endpoints that opt in. It stores the key, scoped to
  the user and endpoint, in Redis with an expiry (24h, say):
  - **First request:** record the key as in progress, run the route, then save the
    response's status and body against the key.
  - **Repeat while in progress:** 409.
  - **Repeat after completion:** the saved status and body, without running the route.
  - **Same key, different body:** 422.

**To decide:**

- A middleware, or a route dependency the endpoints opt into
- Whether a 5xx response is saved, or frees the key so a retry runs again

### 3. Rate limiting

- A sliding window in Redis, with rules per endpoint: tight on sign-in, password and
  verification code endpoints, and on starting a generation run. Keyed by user when
  signed in, else by IP.
- Input size limits on the endpoints that send text to an LLM.

**To decide:** the library (a new dependency), and each endpoint's limits.

### 4. Email and password sign-in

- Sign up and sign in with an email and password, beside Google sign-in.
- **Verify email:** a code sent on sign-up, which the user enters to verify the address.
- **Reset password:** a code sent to the address, which lets the user set a new password.
- Codes are stored hashed, expire in minutes, and allow a few attempts. Passwords are
  hashed with a slow hash such as argon2.

**To decide:**

- The email provider
- Whether auth becomes its own service, possibly written in Go (see Later)

### 5. Generation worker and claim tokens

One PR. Generation moves out of the API into its own service, scaled apart from it, and
a run's owner becomes a claim token instead of the process's worker ID.

**Claim tokens:** each claim makes a new random token and stores it as the run's owner.
The job holds the token, and every ownership check and final write matches on it. A
process that releases a run and claims it back gets a new token, so the old job can't
pass for the new one, which the worker ID can't tell apart today.

**The worker:** a job queue with a separate worker app (`apps/worker/`), so API deploys
never touch running work. Compare `arq` (asyncio, on our Redis, with cron) and Taskiq,
including how each treats a worker that dies mid-job and whether a stopping worker can
hand a job back at once. Written in Python first; a Go port is under Later.

**A job is one segment of a run:** start or resume, then run the graph until it pauses
for review or ends, then acknowledge. A review pause ends the job; the resume is a new
job, and whichever worker takes it continues from the LangGraph checkpoint.

**The queue replaces the lease machinery:**

| Today | With the queue |
| --- | --- |
| Claim with `FOR UPDATE SKIP LOCKED` | The queue delivers each job to one worker, hidden from the rest while held |
| `lease_expires_at` | The acknowledgement deadline |
| Heartbeat | The worker extends that deadline while it works |
| Release on shutdown | The worker hands the job back unfinished |
| 30s pickup loop and the handoff list | The queue redelivers any job not acknowledged in time |
| `pickup_count` and its limit | The delivery count, and a dead-letter queue after N tries |

**The deadline measures liveness, not how long the work takes.** Job length varies too
much to predict: one step after a review takes seconds, four steps on heavy models take
minutes. So the deadline is short and fixed, and a heartbeat extends it for as long as
the worker is alive, whatever the job:

- Heartbeat every N seconds, deadline about 2 to 3 times N (10s and 30s, say), so one
  missed beat is tolerated and a dead worker is noticed within the deadline whatever the
  job's size. The worker never predicts a job's length.
- The heartbeat runs as its own task beside the work, so it beats through a long LLM
  call. Nothing may block the event loop, or the beats stop and the job is redelivered
  while still running.
- A worker that's alive but stuck keeps beating, so the heartbeat can't catch it. The
  per-operation timeouts do (STRONG's 120s, FAST's, Redis and database timeouts), with an
  optional maximum total runtime per job as a backstop.

**The active-run limit:** credits check a user's active runs before a start or resume,
without a lock, so two requests at once can both pass. Consider a lock here (on the
user's row, or in the queue) so the limit holds exactly. Idempotency keys (Phase 2)
already stop a double send from one user.

**Between steps, the job checks two things**, where `_stream_graph` checks for shutdown
today. The graph itself knows nothing about shutdown; this check decides whether a
worker carries on to the next step:

1. Is this worker shutting down? Then stop, the finished step already saved, and hand
   the job back.
2. Does this job still own the run? One `UPDATE ... WHERE id = :run_id AND claim_token =
   :claim_token`. If it changes no row, another worker has the run, so stop without
   writing more. The final status write carries the same check.

**What's left:** the queue delivers at least once, so a job redelivered while a slow
original is still mid-step runs that step twice at worst: the ownership check stops the
original at its next check, but not the LLM call already in flight. Keeping the deadline
short and the heartbeat steady makes it rare.

## Phase 3 — Features

### 1. Persona subscriptions

Any signed-in user, whatever their role, can subscribe to a persona and gets an email
when it publishes a new post. Unsubscribing takes one click, from the email or the
persona's page.

**To decide:**

- The email provider, shared with email sign-in (Phase 2) if that comes first
- One email per post, or a digest
- Whether the email holds the whole post or a summary and a link

### 2. Avatars

A persona's avatar is either an uploaded image or one generated with fal, and either
way it's stored in S3. The persona form uploads or generates the image, then sends the
stored image's URL as `avatar_url` on create or update.
A generated avatar is charged to the creator's balance, like a run.

**To decide:** the S3 host, the fal model and the prompt it's given from the persona's
fields, and the upload's size and type limits. The fal API key comes when this starts.

### 3. Persona from voice or text

The user speaks or types what they have in mind for a persona. An endpoint sends that to
a simple LLM call, which returns a filled persona form without saving anything. The
frontend fills the form's fields with it, and the user edits and creates the persona as
usual. Create only for now.

**To decide:**

- Speech to text in the browser, or audio sent to a transcription model
- How it works for updating an existing persona

### 4. Blog posts and writing examples from voice or text

The same input for describing a blog post to generate, and for a writing example.

### 5. Humanization

Rework the humanize part of the graph from Tyler's samples and notes on humanizing,
possibly as several calls rather than one prompt. Try adding or removing steps in the
generation, different models and different prompts while at it.

### 6. Payments

A creator tops up their balance (a first payment of $5, say), by hand or with
auto-refill, and becoming a creator means adding payment details and that first top-up.
Auto-refill is a user setting: a threshold and an amount. A user without it gets the
low balance warning.
A payment is a `PURCHASE` on the ledger, a new entry type, kept apart from free
`GRANT`s. Charges get a markup in the charge function; see Later › Credit holds.

**To decide:** the payment provider, and whether to use a merchant of record, which
handles sales tax and VAT on digital sales.

## Later

- **Go.** A Go port of the generation worker, or the auth service written in Go
- **Models per request.** The user picks the model for each step instead of the
  fixed tier, charged at that model's price. Needs an Anthropic client beside the
  OpenAI one
- **Credit holds.** With a per-run cost prediction, hold a run's predicted charge when
  it starts and settle it when each segment ends, showing an available balance, so a run
  can't take a balance below zero
- **Model prices in the database.** Prices with the date they take effect, editable
  from the admin panel, and a nightly job that compares them with a published source
  (OpenAI and Anthropic's APIs don't give prices; OpenRouter's model list does) and
  flags a difference rather than changing what users are charged on its own
- **Open-source models.** Models like DeepSeek through a hosted inference provider,
  with LoRA adapters tuned per kind of request, before ever hosting models ourselves
- An optional SSE progress stream, `GET /generate-text/runs/{run_identity}/events`
  (heartbeats, a final `done` event, `Last-Event-ID`), with polling as the fallback
- `GET /generate-text/runs/{run_identity}` also returns the list of steps for the
  progress UI
- A shared `asyncio.Semaphore` capping concurrent LLM calls per worker, sized to the
  provider's rate limits
