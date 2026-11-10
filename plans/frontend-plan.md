# Frontend plan: roles through the feed

The detail for `plan.md` › Phase 1 › item 11: every screen the backend-only PRs
(items 1 to 10) left for the frontend, split into small chained PRs that one session
can build with the project's agents. `plan.md` stays the record of what each backend
item decided; this file says what the frontend does about it.

- [What the frontend is missing](#what-the-frontend-is-missing)
- [Backend changes this needs](#backend-changes-this-needs)
- [Decisions](#decisions)
- [Screens and routes](#screens-and-routes)
- [Conventions for this work](#conventions-for-this-work)
- [The pull requests](#the-pull-requests)
- [How each PR is built](#how-each-pr-is-built)
- [Rule edits](#rule-edits)
- [Running it](#running-it)

## What the frontend is missing

Checked against every backend router and `frontend/src/` on main at `f019726`.

**The generated types are stale.** `src/lib/api-schema.gen.ts` was last regenerated
before roles. It has none of `/admin/*`, `/invites/check`, the `/public` routes or
`/content-items/*`, and `UserResponseDto` there has no role, permissions or balance.
Regenerating it is the first frontend step.

**From items 1 to 10:**

| Backend item | What the frontend lacks |
| --- | --- |
| 1. Roles and credits | Nothing reads `permissions`, `credit_balance_usd` or `is_credit_balance_low`. Every signed-in user sees My Personas, My Posts and Create. A 402 from generate shows "Couldn't write the post. Try again." |
| 2 and 4. Admin panel, role and suspend | No admin pages. Nothing handles a session the server deleted (a grant, a role change, a suspension): the next request is a 401 that shows as a failed page |
| 5. Invites | No `/invite/:code` page and no `/sign-in` page, so every sign-in redirect that carries a code lands on a blank route |
| 6. Reading signed out | `/personas/:id` and `/posts/:id` are behind `RequireAuth` and call the owner routes. No private-persona warning, no "hidden while the persona is private" label |
| 7, 9. Paging, the feed | The homepage is a placeholder. No search box, pager or infinite list |
| 8. Views | Nothing calls `PUT /content-items/{identity}/view` |
| 10. Lists take on paging | `persona-list-query.ts` and `blog-post-list-query.ts` read page 1 of 20 as if it were everything. `BlogPostCard` expects a body the list no longer returns |

**From before roles.** Three gaps, none caused by items 1 to 10:

- **No way to sign in below `lg`.** The sign-in card is only in the right column, which
  is hidden below `lg`. It didn't matter while every page needed a desktop to be useful;
  it does once posts are read signed out on a phone. PR 4 fixes it.
- **Spectral isn't loaded.** `react-styling.md` says loading it "is decided when post
  pages land". Post bodies render in Georgia. Left as it is; see Decisions.
- **`POST /blog-posts` has no screen.** The archive planned it for posts written by
  hand. Every post today comes from a run. Not in this work; see Decisions.

## Backend changes this needs

Three small changes, one PR (PR 1), before any frontend code. Nothing else is planned;
one found along the way goes in the PR that needs it
([Unplanned changes](#unplanned-changes)).

| # | Change | Why the frontend can't do without it |
| --- | --- | --- |
| B1 | A 401 deletes the session cookie. One handler for `UnauthorizedException` in `apps/api/core/exception_handlers.py` answers as today and adds `delete_cookie(SESSION_COOKIE_NAME, path="/")` | The cookie is `HttpOnly`, and `/auth/logout` needs a valid session, so nothing can clear a cookie whose session the server deleted. Until it expires (14 days), every request carries it and every open route answers 401: a suspended user, or a reader just made a creator, can't read a public post without signing in. With B1 the first 401 clears it and the next request is plainly signed out |
| B2 | `persona_name` and `persona_avatar_url` on `BlogPostResponseDto` and `PublicBlogPostResponseDto` | The post page shows its author. The list items already carry both (item 9); the detail result already holds them and the DTOs drop them. Without it a signed-out post page makes a second request for the persona |
| B3 | `is_persona_public` on the blog post summary and both detail responses, from `BlogPostPersonaResult` | Item 6's "Public · hidden while the persona is private" label. The post list no longer comes with every persona (the persona list is paged), so the page can't look the persona up |

PR 1 also adds two dev scripts, both refusing to run outside a local development
database, the way the `e2e/` scripts do:

- **`backend/scripts/dev_seed.py`** fills the database once, up front, with every case
  a screen has to show. Through the services, with no LLM call, and safe to run again
  (it skips what it already added):

  | Seeded | Covers |
  | --- | --- |
  | An admin, with credits | The admin panel; an admin as the target of role and suspend |
  | A creator with a healthy balance, two public personas and a private one, about 50 published public posts, a scheduled post, drafts, and a public post under the private persona | The feed's second page, a persona's page, My Posts with every badge, "hidden while the persona is private" |
  | A creator below the low balance threshold | The banner |
  | A creator at $0 | The 402 |
  | A reader | No create actions, the no-access message |
  | A suspended creator with a public persona and posts | Their content hidden from everyone; Reactivate |
  | A user who signed up and never came back | An empty last-active and a null name in the users table |
  | Ledger rows on the creators: grants, charges, a refund | A user's ledger, signed amounts, a second page |
  | Invites: unused, used, expired, revoked | Every status in the table and on the invite page. The unused one's link is printed, since the code is stored only hashed |

  The users have fixed `example.com` emails, one per case, listed at the top of the
  script.
- **`backend/scripts/dev_session.py`** prints a session id for one of the seeded users,
  by email, as the `e2e/` scripts mint theirs.

The main session runs the seed as soon as PR 1 is built, before any frontend PR. The
browser check in [How each PR is built](#how-each-pr-is-built) and the end-to-end tests
(PR 12) sign in as these users.

**Considered and left out:**

- **The invite's amount on the `?invite=ACCEPTED` redirect.** The page shows the new
  balance from `/users/me` instead.
- **An error code on generate-text refusals.** A 402 is always the balance. A 409 on
  start is always the active-run limit; a 409 on resume gets one message that covers
  all three causes.
- **A creator's own ledger** (`GET /users/me/credit-ledger`). Not in `plan.md`. A
  creator sees a balance and no history until payments (Phase 3 › 6) need it.

## Decisions

Each has a default this plan is written to; Tyler has confirmed D1, D2, D5 and D13 to
D16.
During the run, a new question never stops the work: the session takes the most
conservative option, writes it under **Decisions made** in that PR's description, and
repeats it in the final report. A backend change or a dependency the plan didn't
foresee doesn't stop it either ([Unplanned changes](#unplanned-changes)).

| # | Question | Default | PR |
| --- | --- | --- | --- |
| D1 | Do B1 to B3 and the two dev scripts go ahead? | Yes | 1 |
| D2 | What does the owner see at `/personas/:id`? | What a reader sees, plus Edit, Write a post and Delete, and under the bio a closed "Voice and defaults" section marked "Only you can see this". Opening it shows the background, writing style, sample writing and defaults, from the owner's route (`GET /personas/{identity}`), which already returns them: no new backend route and no second page | 7 |
| D3 | Which posts does a persona's page list for its owner? | The same public posts a reader gets, plus a "Manage posts" link to `/posts?persona=…`, where drafts are | 7 |
| D4 | Where is the balance? | In the user menu, and on a new `/account` page with the email and role. The low balance banner sits above every page | 3 |
| D5 | What does a reader's nav show? | Home and the user menu. A creator made a reader again keeps their personas and posts but has no link to them, and the write routes show the no-access message | 3 |
| D6 | A persona select (the write form, the My Posts filter) with more than 100 personas? | It lists the first 100 by name. `page_size` stops at 100; a searchable select comes when someone has that many | 2 |
| D7 | Does the feed offer Latest beside the score order? | No. `FEED_SCORE` only | 8 |
| D8 | Admin tables are wider than the 720px column | A route sets `isFullWidth` in its handle and its page gets up to 1100px. Below `md` a table scrolls sideways | 5 |
| D9 | Load Spectral? | No. It needs `@fontsource/spectral` (a dependency) or a request to Google Fonts from every reader. Yours to pick | none |
| D10 | A screen for writing a post by hand? | No. Not part of items 1 to 10 | none |
| D11 | How is the frontend tested? | While the screens are built: `fmt:check`, `lint` and `build`, the reviewer, and a browser check of each PR's pages. Then tests, written against the finished screens: Vitest for logic with no screen (PR 11) and Playwright for whole flows against the real backend (PR 12). No component tests | all, 11, 12 |
| D12 | Which model reviews? | `react-reviewer` on Opus at medium effort. `react-coder` stays on Sonnet at low | all |
| D13 | Are the rule edits below approved with this plan? | Yes: the session applies each in the PR named, then runs `fe-docs-auditor` on them | 0 to 7 |
| D14 | A PR finds a bug in an earlier PR's code? | Fixed in the current PR, never on the earlier branch, and named in the top note of the current PR's description ([Unplanned changes](#unplanned-changes)) | all |
| D15 | Do any checks start a real generate run (an LLM call)? | Two, and only these: in PR 3's browser check, one run as the healthy creator (the balance drops without a reload, the charge is on the ledger, the draft is in My Posts); and after PR 9, one pass through write, publish, the feed, the post read signed out, and its view recorded. The PR 12 tests never reach the model | 3, 9 |
| D16 | What may the main session edit? | In PRs 2 to 9, only what [How each PR is built](#how-each-pr-is-built) › step 3 lists. In PRs 0, 10, 11 and 12, also what those PRs give it | all |

## Screens and routes

| Path | Page | Who | PR |
| --- | --- | --- | --- |
| `/` | The feed, with search | Anyone | 8 |
| `/sign-in` | The sign-in card, and the message for a redirect's code | Anyone | 4 |
| `/invite/:inviteCode` | The invite: what it gives, then Google sign-in | Anyone | 4 |
| `/posts/:blogPostIdentity` | A post | Anyone | 7 |
| `/personas/:personaIdentity` | A persona and its public posts | Anyone | 7 |
| `/account` | Email, role and balance | Signed in | 3 |
| `/personas`, `/personas/new`, `/personas/:personaIdentity/edit` | My Personas | `PERSONA_WRITE` | 2, 3 |
| `/posts`, `/posts/:blogPostIdentity/edit` | My Posts | `BLOG_POST_WRITE` | 2, 3 |
| `/write`, `/write/runs/:runIdentity` | Write | `GENERATE_TEXT_RUN_WRITE` | 3 |
| `/admin/users`, `/admin/users/:userIdentity` | Users, and one user | `USER_READ` | 5 |
| `/admin/invites` | Invites | `INVITE_READ` | 6 |

**The nav**, by what the user holds:

| | Signed out | Reader | Creator | Admin |
| --- | --- | --- | --- | --- |
| Home | yes | yes | yes | yes |
| My Personas, My Posts, Create | | | yes | yes |
| Admin | | | | yes |
| Bottom of the rail | Sign in (below `lg`; the card is in the right column from `lg`) | User menu | User menu with balance | User menu with balance |

## Conventions for this work

What every coder on this work followed, until the PR named in [Rule edits](#rule-edits)
moved each into the rules. They're all in `.claude/rules/react-structure.md` and
`react-styling.md` now, and where the two differ, the rules win: review rounds changed
some details (for example, the infinite list's key ends in `'infinite'`).

**Permissions.** The UI checks permissions, never roles, as the backend does:
`hasPermission(user, 'PERSONA_WRITE')` from `features/auth/permissions.ts`, with
`PermissionType` from the generated schema. Only three places check: the nav, the
`RequirePermission` layout route, and a route file passing `canEdit` to a feature
component. A feature other than `auth` never reads the current user. Hiding a control
is a courtesy; the API's 403 is the check, and its `detail` is already a sentence a
toast can show.

**A deleted session.** Two setup files handle it, written by the main session:

- `lib/api-client.ts` gets a response middleware: a 401 from any path but `/users/me`
  sets the `['users', 'me']` query to `null`, and toasts "You were signed out. Sign in
  again." once, only if a user was signed in.
- `app/query-client.ts` retries a query once when it failed with a 401, and never
  otherwise. B1 cleared the cookie on the first answer, so the retry is signed out: an
  open route succeeds, and a guarded one fails for real and its guard redirects.

**Paged lists.** `features/personas/api/user-persona-page-query.ts` (PR 2) is the
pattern.

- A page query takes the route's query params, typed from the generated schema
  (`paths['/personas']['get']['parameters']['query']`), and its key is the resource path
  then the params: `['personas', personaPageParams]`. An invalidation by prefix
  (`['personas']`) covers every page.
- `placeholderData: keepPreviousData`, so a page change keeps the old rows on screen.
- The page, search and sort live in the URL as `page`, `q`, `sort` and `dir`, read and
  written only by the route file, through `useListSearchParams` in
  `lib/use-list-search-params.ts`. Changing the search or the sort returns to page 1.
- The parts: `ListSearchBox` (debounced), `ListPager`, and from PR 5 `DataTable`, all
  in `components/`.
- A list a reader scrolls is infinite: `useInfiniteQuery` over the same route, pages
  flattened and de-duplicated by `identity`, with `InfiniteScrollSentinel` at the end.
  A list someone manages has a pager.

**Owner and public reads.** A view page calls the `/public` route and an edit page the
owner's (`plan.md` › item 6). Their keys differ in the last part:
`['blog-posts', blogPostIdentity]` and `['blog-posts', blogPostIdentity, 'public']`;
the public page is `['blog-posts', 'public', params]`.

**Money and dates.** `formatUsd` in `lib/format-usd.ts`: a balance to cents, a ledger
amount to four places with its sign. Amounts travel as strings, never floats.
`formatDate` and `formatDateTime` in `lib/format-date.ts`.

**States.** A view that loads has four: loading (the `h-… rounded-2xl bg-accent`
blocks the app already uses), empty, error, and not found. `QueryErrorState` in
`components/` replaces the hand-written "not found or failed" block, which exists five
times today.

**Codes with no generated type.** The sign-in redirect's `error`, `invite_error` and
`invite` values aren't in the OpenAPI schema. They're written once, in
`features/auth/sign-in-result-messages.ts`, with a comment naming the backend enums
(`SignInErrorType`, `InviteSignInResultType`). An unknown code gets a general message.

## The pull requests

Chained: each branch starts from the one before, and each PR's base is the previous
branch, so a diff shows only its own work. Merge them in order. Commits are
`type(web): …` for the frontend.

| # | Branch | What it lands | Built by |
| --- | --- | --- | --- |
| 0 | `docs/frontend-plan` (#54) | This plan, `react-reviewer`, the `CLAUDE.md` lines | Main session |
| 1 | `feat/session-cookie-and-post-persona-fields` (#55) | B1 to B3, the two dev scripts, tests | `fastapi-coder`, `be-test-writer` |
| 2 | `feat/web-paged-lists` (#56) | Regenerated types, the list parts, My Personas and My Posts paged and searchable | `react-coder` × 3 |
| 3 | `feat/web-roles-and-credits` (#57) | Permissions, guards, the nav by role, a deleted session, balance, banner, the 402 | Main session, `react-coder` |
| 4 | `feat/web-sign-in-and-invite` (#58) | `/sign-in`, `/invite/:inviteCode`, sign-in below `lg` | `react-coder` |
| 5 | `feat/web-admin-users` (#59) | `DataTable`, the users table, a user's page | `react-coder` × 3 |
| 6 | `feat/web-admin-invites` (#60) | The invites table, create, the link shown once, revoke | `react-coder` |
| 7 | `feat/web-public-reading` (#61) | A post and a persona's page, signed out; the private-persona warning | `react-coder` × 3 |
| 8 | `feat/web-home-feed` (#62) | The feed with search | `react-coder` |
| 9 | `feat/web-post-views` (#63) | Views and how far a post is read | `react-coder` |
| 10 | `docs/frontend-built` (#64) | `plan.md` item 11 marked built, anything the audits left | Main session |
| 11 | `test/web-unit-tests` | Vitest, the testing rules, `fe-test-writer`, unit tests | Main session, `fe-test-writer` |
| 12 | `test/web-e2e-tests` | Playwright, the flows end to end | Main session, `fe-test-writer` × 2 |

### PR 0: the plan and the reviewer

- Commit `plans/frontend-plan.md` and `.claude/agents/react-reviewer.md`.
- `CLAUDE.md` › Agents: add `react-reviewer` beside `react-coder` in the `react-`
  line.
- `CLAUDE.md` › Pull requests: add "A frontend PR is reviewed by `react-reviewer`
  once it's open, after the docs audit. Pass it the base and head refs and what the PR
  is for, never an opinion of the code."
- The four rules sections the reviewer holds every PR to, under
  [Rule edits](#rule-edits) › PR 0, so the coder has read them before PR 2.
- `plan.md` › item 11: one line pointing here.
- Run `fe-docs-auditor` on the changed files.

### PR 1: the session cookie and a post's persona fields

Backend only. `fastapi-coder` writes B1 to B3 and the two dev scripts;
`be-test-writer` covers B1 to B3. No migration. No agent reviews this PR: the tests
and the e2e script are its check.

- **B1:** `UnauthorizedException` gets its own handler; the other standard exceptions
  keep the shared one. Covered for a missing cookie, an unknown session, and an open
  route called with a stale cookie.
- **B2, B3:** `BlogPostPersonaResult` gains `is_public`; the persona is already loaded
  with each post, so no query changes. The three DTOs map the new fields.
- **Checks:** `ruff check`, `ruff format --check`, the full `pytest`, and
  `backend/scripts/e2e/reading_signed_out.sh` still passes.

### PR 2: paged lists

The frontend builds again against the current API, and the two lists it has are paged.

- **Main session first:** start the API, run `npm run api:types`, commit it alone as
  `chore(web): regenerate API types`.
- **Shared layer** (one `react-coder`): `lib/format-date.ts` (moved out of
  `post-status-badges.tsx`), `lib/use-list-search-params.ts`, `ListSearchBox`,
  `ListPager`, `QueryErrorState` and `CardListSkeleton` in `components/`; and the
  hooks: `user-persona-page-query.ts` with `useUserPersonaPage(params)` and
  `usePersonaOptions()` (the first 100 by name, D6), `user-blog-post-page-query.ts`.
  The two old list query files go. `useDeletePersona` drops `exact: true`, which would
  now miss every page.
- **Personas page** (one `react-coder`): `/personas` with search and a pager;
  `PersonaList` takes its page as props.
- **Posts pages** (one `react-coder`): `/posts` with search, the persona filter and a
  pager. `BlogPostCard` takes a `BlogPostSummaryResponseDto` and reads the persona's
  name and avatar from it, so `BlogPostList`, `BlogPostCard`, `BlogPostView` and
  `EditBlogPostForm` lose their `personas` prop, and the pages that only loaded
  personas to pass them stop. `PostStatusBadges` shows "Public · hidden while the
  persona is private" from `is_persona_public`. The write page and the run page read
  `usePersonaOptions()`.
- **Review focus:** the pager at the first, last and only page; a search with no
  results against a list with none at all; the URL after a search on page 3.

### PR 3: roles and credits

- **Main session:** the two setup-file changes under
  [A deleted session](#conventions-for-this-work).
- **`react-coder`:**
  - `features/auth/permissions.ts` and `RequirePermission`, a layout route like
    `RequireAuth`: signed out goes to `/`, and a user without the permission sees
    "Your account can read posts. Creating personas and posts is by invitation for
    now." in place of the page.
  - `app/router.tsx` regrouped by the Screens table.
  - `AppLayout`: nav items by permission. The three copies of the `NavLink` class
    string become one `NavItem` in `components/layout/`.
  - The user menu: the balance for a user who can generate, and an Account item.
    `/account`: name, email, role and balance, or the reader's line above.
  - `LowBalanceBanner` in `features/auth/components/`, rendered by `AppLayout` above
    the page when `is_credit_balance_low` and the user can generate: "Your credit
    balance is low ($0.42). Writing stops when it runs out."
  - `lib/format-usd.ts`.
  - `features/generate-text/generate-text-error-messages.ts`: a 402 is "Your credit
    balance is too low to write. Ask the admin for more credits."; a 409 on start is
    "You already have the most posts being written at once. Wait for one to finish.";
    anything else keeps today's fixed message.
  - The balance refreshes when a run's status changes:
    `features/generate-text/api/use-run-balance-refresh.ts` invalidates
    `['users', 'me']`, and the run view calls it. A key names an API resource, so the
    hook imports nothing from `auth`.
- **Review focus:** each role against each route; a 401 in the middle of a form.

### PR 4: sign-in and invite pages

- `GoogleSignInButton` in `components/`: the `<a href>` to `/api/auth/google/login`,
  with `invite_code` when given one. `SignInCard` uses it.
- `/sign-in`: with no code, the sign-in card, or "You're signed in" and a link home.
  With a code, the message from `sign-in-result-messages.ts`:

  | Param | Message |
  | --- | --- |
  | `error=ACCOUNT_SUSPENDED` | This account is suspended. |
  | `error=EMAIL_TAKEN` | That email already belongs to another sign-in. |
  | `error=SIGN_IN_EXPIRED` | Sign-in took too long. Try again. |
  | `error=SIGN_IN_FAILED` | Sign-in didn't work. Try again. |
  | `invite_error=INVITE_NOT_FOUND` | This invite link isn't valid. |
  | `invite_error=INVITE_USED` | This invite has already been used. |
  | `invite_error=INVITE_EXPIRED` | This invite has expired. Ask for a new one. |
  | `invite_error=INVITE_REVOKED` | This invite is no longer valid. Ask for a new one. |
  | `invite=ACCEPTED` | You're in. You can create personas and write posts. Your balance is $5.00. |

  An invite error that still signed the user in says so and links home.
- `/invite/:inviteCode`, in a new `invites` feature: `invite-status-query.ts` calls
  `POST /invites/check` as a query, with the code in the body and `gcTime: 0` so the
  code isn't kept. Unused: the credit amount and the Google button carrying the code.
  Signed in already: the same, with "It's added to the account you sign in with."
  Used, expired, revoked or a 404: the matching line from the table.
- `AppLayout`: the right column's sign-in card is hidden on these two routes
  (`isSignInCardHidden` in the route handle), and a signed-out nav shows Sign in, to
  `/sign-in`, below `lg`. `RequireAuth` and `RequirePermission` send a signed-out
  visitor to `/sign-in`.
- **Review focus:** the invite code never reaches a query key that outlives the page,
  a toast or a log.

### PR 5: admin, users

A new `admin` feature. The admin routes are in `plan.md` › items 2, 4 and 10.

- **Shared layer** (one `react-coder`): `npx shadcn@latest add table`; `DataTable` in
  `components/` (columns, rows, a sortable header that reports `sort` and `dir`, the
  four states); `isFullWidth` in `AppRouteHandle` (D8); the hooks
  `admin-user-page-query.ts`, `admin-user-query.ts`,
  `admin-credit-ledger-page-query.ts`, `use-grant-user-credits.ts`,
  `use-set-user-role.ts`, `use-set-user-active.ts`; the Admin nav item; the routes with
  stub pages; `AdminSectionNav` (Users, Invites).
- **Users table** (one `react-coder`): `/admin/users`: email, name, role, balance,
  Active or Suspended, joined, last active. Search; sort by joined, email and last
  active; a pager. A row links to the user.
- **A user's page** (one `react-coder`): `/admin/users/:userIdentity`, laid out with
  `PageWithSidebar`. The main column is the ledger: date, type, signed amount, note,
  who made it; search and a pager. The sidebar:
  - the account: email, name, role, balance, status, joined, last active
  - **Grant credits:** amount (over $0, up to $100, two decimals) and a required note
    of up to 500 characters; under it, "A reader becomes a creator and is signed out
    everywhere."
  - **Role:** Reader or Creator, confirmed in a dialog that says the user is signed out,
    and for Creator to Reader that their unfinished runs fail
  - **Suspend** or **Reactivate**, confirmed the same way
  - For an admin: no role or suspend controls, and "An admin's role is changed in the
    database."
- Each mutation invalidates `['admin', 'users']`, and `['users', 'me']` when the admin
  acted on their own account.
- **Review focus:** `DataTable` knows nothing about users; the three write controls are
  three components; the page at 375px.

### PR 6: admin, invites

One `react-coder`. `/admin/invites`:

- The table: name, amount, status, expires, used by, made by, created. Search by
  name; sort by created, name and expires; a pager.
- **New invite:** name, amount (as a grant), an optional note, and the days until it
  expires (7 unless changed, up to 30). On success a dialog shows the link once with a
  Copy button and says it can't be shown again.
- **Revoke** on an unused invite, confirmed. A 409 (it was used meanwhile) shows as a
  toast and the table refreshes.
- `npx shadcn@latest add dialog`, after the `--dry-run` check for new packages.

### PR 7: reading signed out

- **Shared layer** (one `react-coder`): `public-persona-query.ts`,
  `public-blog-post-query.ts`, `public-blog-post-page-infinite-query.ts` and
  `usePublicBlogPostCount(personaIdentity)` (the page route with `page_size=1`, read
  for its total); `InfiniteScrollSentinel` in `components/`; `PublicBlogPostFeed` and
  `FeedPostCard` in `features/blog-posts/components/`, the card with the title and the
  persona as separate links; the two routes moved out of the guard, and `hasSidebar`
  dropped from the persona route.
- **The post page** (one `react-coder`): `/posts/:blogPostIdentity` from the `/public`
  route: title, subtitle, the persona linking to its page, the date, the body. For the
  owner: the status badges, and Edit and Delete when the route says they can write. A
  404 says "Post not found" and links home.
- **The persona page** (one `react-coder`): `/personas/:personaIdentity` from the
  `/public` route, in the 720px column: avatar, name, bio, then `PublicBlogPostFeed`
  for that persona. For the owner: a Private badge when it is, Edit, Write a post and
  Delete, the Manage posts link (D3), and for a private persona "This persona is
  private. Readers can't see it or its posts." `PersonaProfile` goes. Its voice and
  defaults fields become `PersonaVoiceDetails`, which loads the owner's route and
  renders inside the `Collapsible` the app already has, closed until opened, only when
  `is_owner` (D2). A reader's page never requests the owner's route.
- **The warning:** saving a public persona as private asks first: "Make Ada private?
  Its 3 public posts will be hidden until the persona is public again." The edit page
  reads the count from the blog-posts feature and passes it to `EditPersonaForm`. No
  dialog when the count is 0.
- **Review focus:** each page signed out, as a reader, and as the owner; no feature
  importing another for the count.

### PR 8: the homepage feed

One `react-coder`. `/` becomes `PublicBlogPostFeed` sorted by `FEED_SCORE`, under a
`ListSearchBox` whose text is `q` in the URL. Each card shows its persona. The feed
ends with a line saying so; an empty search says nothing matched; an empty feed says
there are no posts yet. Signed out, the sign-in card stays in the right column.

### PR 9: post views

One `react-coder`. A new `content-items` feature:

- `use-record-content-item-view.ts`: `PUT /content-items/{identity}/view`. It changes
  no cached data and reports no error: a view that fails is dropped.
- `hooks/use-read-progress.ts`: the furthest quarter of an element the reader has
  scrolled past, from scroll position alone.
- `ReadProgressTracker`: wraps the post, sends 0 when it opens and each higher quarter
  once. The post page renders it only when the reader isn't the owner (`plan.md` ›
  item 8).
- **Review focus:** the hook measures and the tracker sends, each alone; a short post
  that fits the screen counts as read in full; nothing is sent twice.

### PR 10: marked built

`plan.md` › item 11 says what was built and points here; this file's PR table gets
each PR's number. Whatever the last `fe-docs-auditor` run found goes in.

### PR 11: the test setup and unit tests

The frontend's first tests. The dependencies are approved here: `vitest` in this PR,
`@playwright/test` in PR 12, both dev dependencies.

- **Main session, the setup:** install `vitest`; `npm run test` in `package.json`; the
  config (in `vite.config.ts`, or beside it if that's cleaner); one small test written
  by hand as the pattern. Add `npm run test` to `CLAUDE.md` › Commands and to what runs
  before a frontend commit.
- **Main session, the rules:** a new `.claude/rules/react-testing.md`, owning how the
  frontend is tested, with two sections:
  - **Unit tests:** what gets one (a plain function or a hook with logic and no
    screen), what doesn't (a component, anything the generated types or the build
    already prove), the file beside its source as `<name>.test.ts`, names that say the
    behaviour, and no mocked API.
  - **End-to-end tests:** filled in by PR 12.
- **Main session, the agent:** `.claude/agents/fe-test-writer.md`, the frontend's
  `be-test-writer`: it reads `react-testing.md` first, writes only test files and
  their fixtures, never changes the code under test (it reports what it thinks is a
  bug), and runs only its own test files. One agent for both kinds: the rules file
  holds what differs between them, and each spawn is a fresh context given one kind and
  one set of files, so a unit task and a flow task never share one.
  `react-coder.md` › Tests points to it, and `fe-docs-auditor.md` gains the testing
  row in its ownership table. Run `fe-docs-auditor` on all of it.
- **`fe-test-writer`:** `use-list-search-params` (reading, writing, back to page 1 on a
  new search or sort), `formatUsd` and the date helpers, the feed's de-duplication, the
  read-progress quarters, the sign-in code messages (every code, and an unknown one),
  the generate-text error messages, `hasPermission`.
- **Review:** `react-reviewer`, asked whether each test would fail if the behaviour
  broke.

### PR 12: end-to-end tests

- **Main session, the setup:** install `@playwright/test` and its Chromium;
  `npm run test:e2e`; a config that expects the API on 8000 and starts `npm run dev`;
  a fixture that signs in as a reader, a creator or an admin by setting the `sid`
  cookie from `dev_session.py`, as the users `dev_seed.py` adds; one flow written by
  hand as the pattern. The
  **End-to-end tests** section of `react-testing.md`: one file per flow in
  `frontend/e2e/`, elements found by role and label, never by class, each test making
  what it changes through the API, reading the seeded data but never relying on another
  test's changes, and local
  only, refusing any API that isn't localhost.
- **`fe-test-writer` × 2,** on separate files:
  - Reading: signed out, the feed loads, a search narrows it, a post opens, its
    persona's page opens; a private persona is a not-found page; a reader is shown the
    no-access message at `/write`.
  - Creating: My Personas and My Posts page and search; making a public persona private
    asks first; a creator below the minimum balance gets the 402 message.
  - Admin: the users table sorts and searches; a grant shows on the ledger and the
    balance; suspend then reactivate; an invite is created, its link shown once, then
    revoked.
  - Invites and sign-in: an unused, used and unknown invite link; each `/sign-in` code
    shows its message.
- Google's own sign-in screen isn't tested: the fixture stands in for it.
- **Review:** `react-reviewer`, asked whether each flow can pass while the feature is
  broken, and whether any test depends on another.

## How each PR is built

The same steps for every frontend PR. Parallel work follows `CLAUDE.md` › Running
agents in parallel.

1. **Branch** from the previous PR's branch.
2. **Brief each coder** with: this file's path and the headings to read (its PR, and
   Conventions for this work), the files it owns, and for a page agent the shared
   layer's files and exports. Never paste what the file already says.
3. **Main session's own edits:** `app/query-client.ts`, `lib/api-client.ts`,
   `index.css`, and `npm run api:types`. Nothing else in PRs 2 to 9: the coders write
   the rest (D16).
4. **Check:** `npm run fmt:check`, `npm run lint`, `npm run build`.
5. **Commit, push and open the PR** against the previous branch (`CLAUDE.md` › Pull
   requests). The description says what it lands, what's still to come, and lists
   **Decisions made**. Then this PR's rule edits and what `fe-docs-auditor` finds in
   them, as their own commit.
6. **Review:** `react-reviewer`, with the base and head refs and this file's heading
   for the PR. Nothing about what the session thinks of the code.
7. **Fix** every Blocker and Should fix with `react-coder`, as a separate commit. If
   there was a Blocker, review once more, on the fix commit only. Two rounds at most;
   what's left goes in the description under **Open review notes**.
8. **Browser check:** with the API and `npm run dev` running, one `general-purpose`
   agent opens this PR's pages with the browse skill, at 1280px and 375px, as each role
   the page differs by (`dev_session.py` mints the `sid` cookie). It reports console
   errors, failed requests and broken layout, with screenshot paths, and nothing else.
   Fix what it finds. If the servers or the browser can't be started, skip it, say so
   in the description, and go on.
9. **Next PR.**

### Unplanned changes

None of these stops the chain. Each is made in the PR that needs it and named in a
note at the very top of that PR's description, above everything else, and again in the
final report.

- **A backend change,** of any size, when a screen can't work without it: a missing
  field, a filter or sort, a new route, a migration. It follows `CLAUDE.md` › Running
  agents in parallel: `schema-coder` first if a table changes, then `fastapi-coder`,
  then `be-test-writer`. `ruff check`, `ruff format --check`, `pytest` and, after a
  migration, `pytest -m migration` pass before the frontend that depends on it is
  built, and `npm run api:types` is run again. The top note says what changed and why;
  one that adds a migration, a permission, or changes who can see or do what says so
  in its first line, so it's reviewed first.
- **A new dependency:** the main session installs it (`react-coder` never runs
  `npm install`) and commits `package.json` and the lockfile in that PR. The top note
  names the package and what it's for. This is for this work only; `CLAUDE.md`'s "Ask
  before adding a dependency" stands otherwise.
- **A fix to an earlier PR's code** (D14): made in the current PR. The top note names
  the earlier PR, the file, and what was wrong.

### Keeping the main session small

The main session coordinates; the agents read and write. Its context is compacted
automatically when it fills, and these keep that from losing anything:

- GitHub and git hold the progress, not the conversation. At the start of each PR, and
  whenever unsure where the work stands, run `gh pr list` and `git log --oneline -15`,
  then re-read only this file's heading for the next PR.
- Don't read a coder's files or a full diff into the main session. Take the agent's
  report, run the checks, and let `react-reviewer` read the code.
- Everything worth keeping goes in the PR description as it happens (Decisions made,
  Open review notes, the top note), so the final report is assembled from the PRs.

**When it's all done,** one report: each PR with its link and one line; every unplanned
backend change and dependency; every decision made along the way; open review notes;
rule gaps the reviewer raised that aren't in Rule edits; and anything skipped, with
why.

## Rule edits

Proposed wording, applied in the PR that builds each pattern (D13) and pointing at the
file that PR adds. All in `react-structure.md` unless it says otherwise. All are
applied; the rules files hold the final wording, which the docs audits adjusted.

| PR | Section | What it adds |
| --- | --- | --- |
| 0 | New: **Component boundaries** | "A component, hook or function does one job, said in a sentence without 'and'. Fetching and cache go in `api/`. A timer, observer or scroll listener goes in a hook. Markup and classes go in a component. The URL and navigation belong to the route file, and to the component that calls `mutate`. Motion is classes, never code mixed into data handling. A boolean prop that turns a component into a different one is two components. A block written a third time becomes a shared one." |
| 0 | New: **States** | "A view that loads data has a loading, an empty and an error state, and a not-found state when it's read by identity. A button is disabled while its request runs. A destructive action confirms in an `AlertDialog` first; `delete-persona-button.tsx` is the pattern (since replaced by `ConfirmActionButton`)." |
| 0 | New: **Accessibility** | "A link navigates and a button acts. No interactive element sits inside another. Every control has a label, and an icon-only button an `aria-label`. Headings descend in order. A sortable column says its sort with `aria-sort`. Colour is never the only signal." |
| 0 | New: **Trust** | "Hiding or disabling a control is a courtesy, never the check: the API refuses, and the page handles the refusal. A secret such as an invite code stays out of query keys that outlive the page, toasts and logs. No `dangerouslySetInnerHTML`." |
| 0 | Toasts | "What the user reads is in sentence case, and a failure says what to do next." |
| 2 | New: **Paged lists** | The Paged lists paragraph under Conventions for this work, shortened, with `user-persona-page-query.ts` as the pattern |
| 2 | States | `QueryErrorState` and `CardListSkeleton` as the parts to build the states from |
| 2 | Features | "A hook that more than one feature uses goes in `lib/`, as `use-<name>.ts`." |
| 2 | The folder tree | `lib/format-date.ts`, `lib/use-list-search-params.ts`, and the shared list components |
| 3 | New: **Permissions and sessions** | The Permissions and A deleted session paragraphs, shortened, with `require-permission.tsx` as the pattern |
| 3 | Mutations | "A query key names an API resource, so a hook invalidates another feature's resource by its key, without importing from that feature." |
| 3 | Toasts | The signed-out toast as the one toast a query's failure can cause; the 402 and 409 messages beside the existing generate-text exception |
| 4 | Sign-in | The `/sign-in` page and its codes, and `POST /invites/check` as a query |
| 4 | Talking to the API | "A value the API sends outside the schema, such as a redirect's code, is written once in the feature, with a comment naming the backend enum." |
| 4 | Routing | "`hasSidebar` is the one field so far" becomes a pointer to `AppRouteHandle`, which now has `isSignInCardHidden` |
| 4 | `react-styling.md` › Layout | The sign-in card is hidden on a route that shows its own, and a signed-out nav has Sign in below `lg` |
| 5 | `react-styling.md` › Layout | `isFullWidth`, and "a table scrolls sideways below `md`" |
| 7 | Queries | The owner and `/public` key shapes; the infinite list |
| 7 | `react-styling.md` › Shape and type | "Loading it … is decided when post pages land" becomes "Spectral isn't loaded; post text falls back to Georgia" (D9) |

Each also means a line in `react-coder.md` only where it adds a kind of file the
agent's lists don't cover. `fe-docs-auditor` checks that.

## Running it

Before starting: `backend/.env` pointing at the local database. Docker's Postgres and
Redis are already running.

The message to start the session with:

> Read `plans/frontend-plan.md` and build it, PR 0 to PR 12, in order, following
> How each PR is built. You may create branches, commit, push and open pull requests
> for this work; never push to `main` and never merge. Postgres and Redis are already
> running in Docker; start the API and the frontend dev server yourself when a step
> needs them. Don't stop to ask: follow the Decisions table and record anything new
> under Decisions made. If a PR needs a backend change or a new dependency the plan
> didn't foresee, make it in that PR and note it at the top of the PR's description,
> as Unplanned changes says. Finish with the report the plan describes.
