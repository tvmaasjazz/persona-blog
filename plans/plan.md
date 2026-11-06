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
frontend comes in item 11.

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
- Granting credits makes the user a creator: `backend/scripts/grant_credits.py` or
  the admin panel (item 2). The admin sets a reader or creator's role in the panel
  (item 4); making an admin is SQL. Changing a role in code deletes
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

Built in #39. Admin-only endpoints under `/admin`, in their own router, for the admin panel's
pages (item 11): a table of users, each linking to a user page with the account, a
grant form and the ledger.

- **Permissions,** held by the admin only and checked per route: `USER_READ` (any
  user's account: email, role, balance), `CREDIT_READ` (any user's ledger) and
  `CREDIT_WRITE` (granting). `USER_WRITE` comes with item 4. A user's public profile,
  when there is one, gets its own `PROFILE_READ`.
- **Admin services:** `AdminUserService` and `AdminCreditService` in `libs/admin/`
  (`fastapi-structure.md` › Services). A balance still only changes through
  `CreditLedgerService`.
- **Users:** `GET /admin/users`, every user but the system user, newest first, with
  their role and balance. No search or pagination yet; item 10 pages it.
  `GET /admin/users/{user_identity}` for the user page.
- **A user's ledger:** `GET /admin/users/{user_identity}/credit-ledger`, every row,
  newest first, until item 10 pages it.
- **Grant credits:** `POST /admin/users/{user_identity}/credit-grants`, an amount up to
  $100 and a required note, written as a `GRANT` on the ledger. A reader becomes a
  creator, and their sessions are deleted after the response, so they sign in with the
  new role. Sessions are found through a per-user set of session ids in Redis. The
  system user is refused with a 409; an inactive user can be granted.
  `backend/scripts/grant_credits.py` stays for granting without the panel, through the
  same service.

### 3. Run status guards (backend)

Built in #40, before item 4, which fails runs that are still going. Each write that
moves a generate-text run or step to a new status applies only from the statuses it's
meant to leave, so a late write from a job that's being stopped can't undo a newer one:

| Write | Applies only when | Otherwise |
| --- | --- | --- |
| `start_run` | The run is `PENDING` | Returns `False`, and the job ends without running the graph; an unknown run still raises `NotFoundException` |
| `create_step` | The run is `RUNNING` | Raises, and the job ends |
| `complete_step` | The run and the step are `RUNNING` | Does nothing; the step is charged only when this write completed it, and an unknown step still raises `NotFoundException` |
| `record_awaiting_review` and `fail_step` (step) | The step is `RUNNING` | Does nothing; an unknown step still raises `NotFoundException` |
| `complete_run` and `record_awaiting_review` (run) | The run is `RUNNING` | Does nothing; an unknown run still raises `NotFoundException` |
| `fail_run` | The run is `PENDING`, `RUNNING` or `AWAITING_REVIEW` | Does nothing. Today it skips only a `FAILED` run, so it would fail a `COMPLETED` one |

- `fail_run` also fails the run's `RUNNING` step, in the same transaction.
- Claiming a paused or an expired run already checks the status.
- **How a failed run's job stops:** failing the run clears its lease. The job stops at
  whichever comes first: its LLM call returns, `complete_step` finds the step already
  failed and charges nothing, and the next `create_step` raises; or the next lease
  renewal (every 15 seconds) fails and cancels the job mid-call. At most the call in
  flight is lost, and it's never charged.
- This also closes the same gap when a lease is lost today.
- The rule is in `fastapi-structure.md` › Querying and writing: a write that moves a
  row to a new status names the statuses it moves from.

### 4. Set a role and suspend (backend)

Built in #41. Two admin actions under `/admin`, held to the admin by a new
`USER_WRITE`:

- **Set a role:** `PUT /admin/users/{user_identity}/role` with `{"role": "READER"}` or
  `"CREATOR"`. Only a reader or a creator can be changed, and only to one of those two:
  making an admin stays SQL, so a stolen admin session can't make more, and an admin,
  yourself included, can't be demoted or locked out. An admin target returns 409; the
  system user returns 404, as on the other admin routes.
- **Suspend:** `PUT /admin/users/{user_identity}/active` with `{"is_active": false}`, or
  `true` to reactivate. The same admin and system user rules apply.
- **Setting the value the user already has** returns 200 and does nothing.
- **After the change commits,** as after-response tasks:
  - the user's sessions are deleted, so the change applies at once;
  - suspending, or demoting a creator to a reader, fails the user's `PENDING`, `RUNNING`
    and `AWAITING_REVIEW` runs through `fail_run`, with `USER_SUSPENDED` or
    `USER_ROLE_CHANGED`. A reader can't resume a run, so it would only cost LLM calls.
    Failing runs after the commit means a suspension that rolls back never killed a
    run; a failure there is only logged, and the user is still suspended and signed out.
- **A suspended user's content is hidden** where it's read: their personas and posts
  are treated as private, the way a private persona's posts are (item 6). Nothing is
  changed on the rows, so reactivating shows them again at once.
- **Reactivating** restores the account as it was (role, credits, content); the user
  signs in again. Failed runs stay failed.
- **Sign-in errors redirect to the frontend** with a code, rather than leaving the
  browser on the API's JSON: `{frontend_url}/sign-in?error=ACCOUNT_SUSPENDED`, and
  likewise `EMAIL_TAKEN`, `SIGN_IN_EXPIRED` and `SIGN_IN_FAILED`.
- **Placement:** `AdminUserService.set_user_role()` and `set_user_active()` write the
  user row themselves, since only an admin makes these writes (the rule change below).
  Failing runs goes through `GenerateTextRunService.fail_run()`, from a
  `fail_user_unfinished_runs` task in `libs/generate_text/after_response_tasks.py`.
- **Rule change** in `fastapi-structure.md` › Services: an admin service writes through
  the owning domain's service when that service already makes the same write; a write
  only an admin makes is the admin service's own.

### 5. Invite links (backend)

Built in #42. The admin creates an invite carrying a name, a credit amount,
an optional note and an expiry, and gets back its link. There's no email in the app:
the admin copies the link and sends it by email or text. The name is required and says
who it's for, since the invite isn't tied to an email, so the list shows who each link
went to.

- **Permissions:** `INVITE_READ` and `INVITE_WRITE`, held by the admin only.
- **Table `pb_invite`:** the name, `credit_amount_usd` (over $0, up to $100, as grants),
  the note, `code_hash` (unique), `expires_at`, `used_at`, `used_by_user_id` and
  `revoked_at`. `pb_credit_ledger` gets a nullable `invite_id`, so the invite's grant is
  found by key rather than by its note.
- **The code** is 16 random bytes, about 22 characters in the link. Only its SHA-256 is
  stored; a slow hash only matters for a guessable secret. The link is
  `{frontend_url}/invite/{code}`, built from `AuthSettings.frontend_url`, and is shown
  once, when it's created. A lost link is revoked and replaced.
- **Admin routes:** `POST /admin/invites` (expires in 7 days unless
  `expires_in_days`, up to 30, says otherwise) returns the identity and the link;
  `GET /admin/invites` lists every invite, newest first, with its status (unused, used,
  expired, revoked) and who used it; `POST /admin/invites/{invite_identity}/revoke`
  sets `revoked_at` on an unused invite, and a used one returns 409.
- **Checking a code:** `POST /invites/check` with `{"code": ...}`, an open route,
  returns the status and the credit amount, not the name or note, and a 404 for an
  unknown code. It's a `POST` so the
  code stays out of API URLs and logs before it's used. The invite page calls it first
  and shows Google sign-in only for a valid code.
- **Using it:** `/auth/google/login?invite_code=...` checks the code again: an unknown
  or no longer valid code redirects (303) to `{frontend_url}/sign-in?invite_error=...`
  without going to Google; otherwise it carries the code in the OAuth state.
  At the callback, once the user is found or created, whether they just signed up or
  already had an account, one update marks the invite used, guarded on unused,
  unexpired and unrevoked, so it's used once. In the same transaction a reader becomes a
  creator (an admin keeps their role) and the credits are a `GRANT` on the ledger, with
  `invite_id`, the invite's note or "Invite: <name>", and the admin who made the invite
  as its author. The session is created after, with the new role.
- **Redirects:** `?invite=ACCEPTED` on success; a code that fails at the callback still
  signs the user in, with `?invite_error=INVITE_EXPIRED`, `INVITE_USED` or
  `INVITE_REVOKED`; the login refuses an unknown code with `INVITE_NOT_FOUND`. Both go to
  `{frontend_url}/sign-in`, and a sign-in with no invite still goes to the frontend's
  root.
- **Placement:** `AdminInviteService` in `libs/admin/` creates, lists and revokes, since
  only an admin does; `InviteService` in `libs/invites/` checks and uses a code. Making a
  reader a creator now has two callers, a grant and an invite, so it moves to one
  method both call.

### 6. Reading signed out (backend)

One PR. A shared link to a persona or a post works for anyone, signed in or not. It
pages nothing, so a reviewer only has to think about who can see what.

- **Two routes for each, one shape each.** The owner's route returns the full record
  for the edit page; an open `/public` route beside it, in the same router, returns
  what a reader sees:

  | Route | Who | Returns |
  | --- | --- | --- |
  | `GET /personas/{persona_identity}` | The owner, `PERSONA_READ`; 404 for anyone else | Every field |
  | `GET /personas/{persona_identity}/public` | Anyone, signing in optional | Name, bio, avatar, `is_public`, dates and `is_owner`; not the background or writing settings |
  | `GET /blog-posts/{blog_post_identity}` | The owner, `BLOG_POST_READ`; 404 for anyone else | The post |
  | `GET /blog-posts/{blog_post_identity}/public` | Anyone, signing in optional | The post and `is_owner` |

  A `/public` route shows the signed-in owner their own private persona or post, and
  anyone else gets a 404 for one. `is_owner` tells the view page whether to show an
  edit link. The frontend's URL picks the route, so a pasted link or a refresh never
  has to guess: the view page (`/personas/:id`) always calls `/public`, and the edit
  page (`/personas/:id/edit`) the owner's route. The `/public` routes join
  `OPEN_ROUTES` in `test_app_factory.py`. The owner's own lists, writes and generation
  keep their permissions.
- **Optional sign-in:** with no session cookie the caller is signed out. A cookie
  whose session is expired or invalid is still a 401, as on every other route, and the
  frontend sends the reader to sign in again.
- **The read permissions stay.** Every role that signs in keeps `PERSONA_READ` and
  `BLOG_POST_READ`, but the open routes don't check them for now. They're kept for
  later rules that may check them again, such as showing a signed-out reader only half
  a post.
- **A post shows to others only if its persona is public too.** Making a persona
  private changes no post: its posts keep `is_public = true` but are treated as
  private, so they leave the feed and a link to one returns a 404 to anyone but the
  owner. Making the persona public again brings back exactly the posts that were public,
  at once. Every query that shows posts to others checks both flags, as
  `ContentItemQueryUtils.build_accessible_condition` does today.
- **Editing a post under a private persona:** a private persona can't make a post
  public, but a post that's already public stays editable and keeps `is_public = true`;
  only a change from private to public is refused. A post's response returns
  `is_public` as stored, so the owner sees which posts come back, and the frontend,
  which already has the persona, labels one "Public · hidden while the persona is
  private".
- **The frontend warns** when a persona is made private: "Its public posts will be
  hidden until the persona is public again." The number of them comes later, from item
  7's paging with a public filter and a total.
- A suspended owner's personas and posts stay hidden from others (item 4).

### 7. Paging and search (backend)

Built in #46, with a validation fix in #47. One way of paging, searching, sorting and
filtering every collection in the app, used first by a persona's page. Item 10 moves
today's lists onto it. The pattern is in `fastapi-structure.md` › Paged routes, so
items 9 and 10 follow it.

- **Request:** a `GET` with flat query params. Every paged route's `<Entity>PageQueryDto`
  extends a shared `BasePageQueryDto`:

  | Param | Default | Allowed |
  | --- | --- | --- |
  | `page` | `1` | 1 and up |
  | `page_size` | `20` | 1 to 100 |
  | `search` | none | stripped, up to 200 characters |
  | `sort_by` | the route's own | the route's `<Entity>SortType`, declared on its own DTO |
  | `sort_direction` | `DESC` | `ASC` or `DESC` |

  Paging is by offset. A page number and a total suit the admin tables and item 6's
  warning count, and the feed's changing score (item 9) wouldn't keep a cursor steady
  anyway. A post arriving between two page loads can push a row onto the next page;
  that's accepted.
- **Response:** every `<Entity>PageResponseDto` extends a shared `BasePageResponseDto`,
  so each page has its rows under a plural field and the same `pagination`:

  ```json
  {"blog_posts": [...], "pagination": {"page": 1, "page_size": 20, "total": 134}}
  ```

  Plain subclasses, not a generic `BasePageResponseDto[T]`, which would name its schemas
  `BasePageResponseDto_BlogPostResponseDto_` in the generated types and couldn't name the
  rows field. A `PaginationResult` mirrors it in the lib.
- **Sort:** a paged route's `<Entity>SortType` enum names the columns it can be sorted by, so
  any other is a 422 and the frontend gets the allowed values from the generated
  types. Every sort is the chosen column, `NULLS LAST` either way, then `id` in the same
  direction, so pages keep a fixed order.
- **Filters:** flat, typed fields on the route's query DTO, one value each, named the
  same way on every paged route:

  | Kind | Name | Example |
  | --- | --- | --- |
  | Equals | `<field>` | `persona_identity=…`, `is_public=true` |
  | Any of | plural `<fields>`, repeated | `roles=ADMIN&roles=WRITER` |
  | Range | `<field>_from` (inclusive), `<field>_to` (exclusive) | `created_at_from=2026-10-01` |
  | Has a value | `has_<field>` | `has_published_at=false` |

  A missing field filters nothing; `null` never means "where it's null", which is what
  `has_<field>` is for. Filters only narrow: who may see what
  (`ContentItemQueryUtils.build_accessible_condition`, ownership) stays in the
  service's base query and is never a filter. A user-built filter menu, if one comes,
  adds a `POST …/search` body of `{property, operator, value}` checked against the
  same `PaginationConfig`, with the flat fields kept for filters a page fixes.
- **Search:** the phrase is split into words, at most 8, and each word must match at
  least one of the route's search fields, case-insensitively (`ILIKE`, with `%` and `_`
  escaped so they match themselves). No full-text search yet: a `pg_trgm` index speeds
  up the same query when tables grow, and full-text search, for ranking and stemming,
  would change nothing in the contract.
- **Names:** a paged route is a page, not a list: `find_public_blog_post_page`,
  `FindPublicBlogPostPageInput` and `PublicBlogPostPageResponseDto`. The classes each
  route extends are `Base…` (`BasePageQueryDto`, `BasePageInput`, `BasePageResponseDto`),
  and the shared pieces that do the paging are `Pagination…`. `List` names stay only on
  a route that returns everything at once.
- **One config per paged route, one call per service:** a `PaginationConfig` declares
  what a route searches, sorts and filters by, and the service makes one
  `PaginationService.find_page` call (`fastapi-structure.md` › Paged routes). The total
  comes from `count(*) OVER ()` on the page query, which Postgres computes before
  `LIMIT`. Running a count beside the page on a second session would cost a second
  connection and could disagree with the page, to save one round trip.
  `SortDirectionType` and `FilterOperatorType` live in
  `libs/core/types.py`, since the libs use them and can't import from `apps/`.
- **A persona's page:** `GET /blog-posts/public`, an open route on `OPEN_ROUTES`,
  lists the posts its caller may see under `build_accessible_condition`: other
  people's published public posts of public personas, and all of the signed-in
  caller's own, as the `/public` reads in item 6 do. It filters by `persona_identity`,
  sorts by `PUBLISHED_AT` (the default) or `TITLE`, and searches the title and
  subtitle. Rows leave out the body, which a list doesn't show, and search skips it
  too: matching a body is worth it only once search can weigh it against the title. A
  later owner's toggle to see the page as readers do is a flag that drops "all of the
  caller's own", not a column filter. It's declared before
  `/{blog_post_identity}`, so `public` isn't read as an identity. No migration: a
  `(persona_id, published_at)` index waits until the page is slow.

### 8. Post views and the feed's order (backend)

One PR. Simple counts of how posts are read, and a score to order the homepage by
(item 9).

- **Views:** a view belongs to a content item, not a blog post, so later content types
  get views too. One view per viewer, per item, per UTC day, holding the furthest
  quarter read. A view by the item's own author isn't recorded: the frontend doesn't
  send one, and the backend ignores one that arrives.
  - Each is a row in `pb_content_item_view`: by user when signed in, else by the
    anonymous user key. Signed-out rows are the history of what was read and how far,
    without saying who.
  - **The anonymous user key** is a hash of the client IP (the hop Railway's proxy
    adds, not one the client sent), the user agent and a salt. The salt is random,
    kept only in Redis, and replaced each day, so once it expires a stored key can't
    be traced back to an IP, and nothing links a reader across days. No cookie.
    Readers who share an IP and browser count as one; that's accepted. The key is
    worked out by a dependency beside the optional auth user, not by anything
    content-specific, so another signed-out feature can use it.
- **Recording:** one open route, `PUT /blog-posts/{blog_post_identity}/view` with
  `read_percent` (0, 25, 50, 75 or 100). The frontend calls it with 0 when a post opens
  and again at each quarter as the reader scrolls. It creates today's view or updates
  it, and the stored percent only goes up. Signed-out views can be inflated until rate
  limiting (Phase 2 › 3); that's accepted.
- **Engagement:** each view adds 1, plus 3 times the share of the post it read, so a
  half read adds 1.5 more and a full read 3 more. Partial reads count for what they
  read. The item keeps its view count and its summed read shares apart, so new weights
  rescore it without reading its views.
- **The score doesn't change with time,** so it's a stored, indexed column and the
  feed's query only sorts by it:
  `log10(engagement + 1) + (hours from a fixed date to published_at) / 24`. A newer
  post starts higher, so a post a day older needs 10 times the engagement to tie, and
  no score ever needs to age. There's no window: a read counts for good, and age
  outweighs it.
- **When the score is written:** when `published_at` is set, and in the same statement
  that adds a view or raises how far it was read, from the engagement that view adds. An
  unpublished item has no score. The weights and the 24 hours are settings; after
  changing one, `scripts/recompute_feed_scores.py` rescores every item from its view
  count and summed read shares.
- **Where it's kept:** the view count, summed read shares and score live in
  `pb_content_item_engagement`, one row per content item, not on the content item
  itself. A view write then rewrites a small row and its own indexes, not the content
  item's row and every index on it.
- Authors seeing their posts' views and reads waits for Phase 3 › 7.

### 9. The homepage feed (backend)

One PR, after items 7 and 8. Every public post, ordered by the score (item 8), paged
and searchable with item 7's pattern. An open route, like a persona's page.

### 10. Lists take on paging (backend)

One PR, after item 7. The five lists the app has today move to item 7's paging and
search, so the frontend's shared table and pager (item 11) has one shape to build
against:

- `GET /admin/users`, searching email and name
- `GET /admin/invites`, searching the name
- `GET /admin/users/{user_identity}/credit-ledger`, newest first
- `GET /personas`, the signed-in user's own personas
- `GET /blog-posts`, the signed-in user's own posts

Which fields each list searches, and whether the ledger needs a search at all, are
decided with item 7's pattern in hand.

### 11. Frontend

Everything the backend-only PRs added, before the deploy:

- **Roles:** a reader sees no create, edit or generate actions, and a 403 shows a
  message rather than an error.
- **Credits:** the balance on the profile, the low balance banner, and the 402 message
  when a run is refused.
- **Admin panel:** users with their role and balance, a user page with granting credits
  with a note, setting the role and suspending (item 4), the user's ledger, and
  creating, listing and revoking invites, with the new link shown once to copy.
- **Invite sign-up:** the link's page checks the code, then signs the user in with
  Google, carrying the code (item 5).
- **One sign-in result page** reads `error`, `invite_error` and `invite` from the
  sign-in redirect and shows a message for each code: a suspended account, an email
  already in use, an expired or used invite, or the credits an invite gave.
- **Homepage:** the feed (item 9), replacing My personas as the start page, with search
  and recording views and how far a post is read (item 8). The feed scrolls
  infinitely over item 7's offset pages, dropping any post it already shows, since a
  read can move a post across a page boundary between loads.
- **A persona's page:** its public posts (item 7), reached from a post or the feed, and
  readable signed out (item 6). Making a persona with public posts private warns that
  they'll be hidden.
- The table, search box and pager every list shares (items 7 and 10).

Probably more than one PR, split by area: the shared pieces and roles and credits first,
then the admin panel and invites, then the homepage and persona pages.

### 12. Deploy readiness

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
- [ ] The frontend at `personagora.com` and the API at `api.personagora.com`, which
  are the same site, so the API's cookies are first-party. Check once that Safari keeps
  the session cookie past 7 days: it caps cookies from a subdomain whose IP differs
  from the main site's
- [ ] Check which header Railway's proxy sets to the client's IP, and that a client
  can't set it, since signed-out views are counted by it (item 8)

### 13. Initial deploy

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
  signed in, else by IP alone, from the client IP dependency that the anonymous user key
  (Phase 1 › 8) uses. Not by that key: the client sets its user agent, so changing it
  would give each request a new limit.
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

### 7. Likes, tags and reading history

What readers do with a post, beyond reading it, and what they've read.

- **Likes:** a signed-in user likes or unlikes a post, one like per user per post. A
  like is another term in the feed's engagement (Phase 1 › item 8), with its own weight
  setting.
- **Author stats:** an author sees each post's views, how far they were read, and its
  likes, from the engagement row (Phase 1 › item 8).
- **Tags:** a post has tags, set by its author or suggested by an LLM call when it's
  generated or published, which the author can edit. The feed and a persona's page
  filter by them with the "any of" filter (Phase 1 › item 7).
- **Reading history:** the signed-in view rows (Phase 1 › item 8) already say who read
  what and how far, so a signed-in reader can see what they've read, pick up a post where they
  left off, and have posts they've finished marked or moved down in the feed.
- **Popular personas:** a column beside the feed, ordered by a persona's score from
  its posts' scores, such as its best post's or a sum, so it's recent and engaged like
  the feed.

**To decide:**

- Whether a like counts toward the global score or only toward a reader's own feed
- A fixed tag list, or free tags merged by the LLM call
- Whether the feed becomes personal, weighted by the tags a reader views and likes.
  A personal order can't be stored per post, so the stored global score becomes the
  pool a personal order is picked from

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
