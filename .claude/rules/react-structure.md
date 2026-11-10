---
paths:
  - "frontend/**/*.ts"
  - "frontend/**/*.tsx"
---

# Frontend structure

React 19 + Vite + TypeScript. Organized by feature, not by technical layer, the same
way the backend is organized by domain. No global `hooks/` or `api/` folder.

| Concern       | Choice                                                         |
| ------------- | -------------------------------------------------------------- |
| Routing       | React Router, library mode (`createBrowserRouter`)             |
| Server state  | TanStack Query                                                 |
| API types     | Generated from FastAPI's OpenAPI schema by `openapi-typescript` |
| API client    | `openapi-fetch`, one instance in `src/lib/api-client.ts`       |
| Components    | shadcn/ui (Radix), source in `src/components/ui/`              |
| Icons         | `lucide-react`                                                 |
| Toasts        | `sonner`, through shadcn's `Toaster`: see › Toasts             |
| Forms         | TanStack Form, validated with Zod: see › Forms                 |
| Styling       | Tailwind v4 with design tokens: see `react-styling.md`         |

Ask before adding a dependency, and before any global client state library
(Zustand, Redux, Jotai). Server data lives in TanStack Query and UI state in
`useState`; nothing so far has needed more.

```
frontend/src/
├── main.tsx                   # createRoot, renders <AppProviders> + <RouterProvider>
├── index.css                  # Tailwind entry and design tokens
├── app/
│   ├── providers.tsx          # AppProviders: QueryClientProvider, Toaster
│   ├── query-client.ts        # the one QueryClient and its defaults
│   └── router.tsx             # the route tree
├── routes/                    # one file per page, composed from features
│   ├── home-page.tsx          # HomePage
│   └── personas-page.tsx      # PersonasPage
├── features/
│   └── auth/                  # a feature: one area of the product, like personas/
│       ├── api/
│       │   ├── current-user-query.ts   # currentUserQueryOptions, useCurrentUser
│       │   └── use-sign-out.ts         # useSignOut mutation
│       ├── components/
│       │   ├── require-auth.tsx        # RequireAuth route guard
│       │   ├── require-permission.tsx  # RequirePermission route guard
│       │   └── sign-in-card.tsx        # SignInCard
│       ├── hooks/             # hooks with no API call, if the feature has any
│       ├── permissions.ts     # hasPermission
│       └── <what-it-holds>.ts # plain helpers for this feature only, like run-steps.ts
├── components/
│   ├── ui/                    # shadcn/ui, added with the CLI, never hand-created
│   ├── form/                  # the form layer: useAppForm, field components
│   ├── layout/                # app shell and page layouts: AppLayout, PageWithSidebar
│   ├── confirm-action-button.tsx  # ConfirmActionButton
│   ├── data-table.tsx         # DataTable
│   ├── google-sign-in-button.tsx  # GoogleSignInButton
│   └── list-pager.tsx         # components more than one feature uses, like the list parts
└── lib/
    ├── api-client.ts          # apiClient: the openapi-fetch instance
    ├── api-error.ts           # ApiError, createApiError, apiErrorMessage, isSessionEndedError
    ├── api-schema.gen.ts      # generated from /openapi.json, never hand-edited
    ├── format-date.ts         # formatDate, formatDateTime
    ├── use-debounced-callback.ts
    ├── use-list-search-params.ts
    └── utils.ts               # cn(), from shadcn
```

## Features

A feature is one area of the product: `auth`, `personas`, `blog-posts`,
`generate-text`. Name it after the backend domain it talks to when there is one, in
kebab-case: backend `generate_text` is feature `generate-text`. Create only the
subfolders a feature uses.

A React hook that only one feature uses and that makes no API call goes in its
`hooks/`, like `generate-text/hooks/use-unsaved-run-guard.ts`. Hooks that call the API
stay in `api/`. A hook with no API call that more than one feature uses goes in
`lib/`, as `use-<name>.ts`.

Plain functions and constants that only one feature uses (no React, no API call) go
in a kebab-case `.ts` file at the feature root, named for what it holds:
`generate-text/run-steps.ts` holds the step names and the text built from a run. One
used by more than one feature moves to `lib/`.

A feature never imports from another feature. When a page needs two features, the
route file in `routes/` composes them, the way a backend lib composes two services
instead of one domain importing another. What more than one feature needs moves to
`components/` or `lib/`.

`routes/` files are thin: they lay out feature components and read route and search
params. A route never calls `apiClient` and holds no business logic. It may call
features' query hooks to pass one feature's data into another as props, or to choose
which feature's component to render, which is how it composes them: `write-page.tsx`
reads `usePersonaOptions()` and hands the personas to the generate form.

No barrel `index.ts` files. Import from the file that defines the thing.

## Component boundaries

A component, hook or function does one job, said in a sentence without "and".

- Fetching and cache go in `api/`.
- A timer, observer or scroll listener goes in a hook.
- Markup and classes go in a component.
- The URL and navigation belong to the route file, and to the component that calls
  `mutate`.
- Motion is classes, never code mixed into data handling.
- A boolean prop that turns a component into a different one is two components.
- A block written a third time becomes a shared one.

## Talking to the API

The backend is reached only through `apiClient`, and only from a feature's `api/`
folder. Components never call `fetch`, `apiClient`, or `axios`. They call the hooks
in `api/`.

```ts
// src/lib/api-client.ts
import createClient from 'openapi-fetch'

import type { paths } from '@/lib/api-schema.gen'

export const apiClient = createClient<paths>({ baseUrl: '/api' })
```

Request and response types always come from `api-schema.gen.ts`, never from a
hand-written interface that mirrors a backend DTO. A value the API sends outside the
schema, such as a redirect's code, is written once in the feature, with a comment
naming the backend enum. When the backend changes, run
`npm run api:types` with the backend API running on port 8000 and commit the
regenerated file. A type error it causes is the change working as intended.

In dev, Vite proxies `/api/*` to the API on `localhost:8000` and strips the `/api`
prefix, so the browser sees one origin and the session cookie needs no CORS. The
backend routes themselves have no `/api` prefix.

### Queries

Each query is a `queryOptions` object plus a hook that uses it. Export both, so
route guards and prefetching can reuse the options without the hook:

```ts
// src/features/auth/api/current-user-query.ts
export const currentUserQueryOptions = queryOptions({
  queryKey: ['users', 'me'],
  queryFn: findCurrentUser,
})

export function useCurrentUser() {
  return useQuery(currentUserQueryOptions)
}
```

- Query keys start with the backend resource path, split on `/`: `GET /users/me` is
  `['users', 'me']`, `GET /blog-posts/{identity}` is
  `['blog-posts', blogPostIdentity]`.
- A failed request throws `createApiError(error, response)` from `lib/api-error.ts`:
  an `ApiError` carrying the HTTP `status` and the body's `detail`, so a caller can
  tell a 409 from anything else. The one exception is the 401 below.
- A 401 from `/users/me` means signed out. Its query function returns `null` rather
  than throwing, so `useCurrentUser()` gives the user or `null`, never an error state.
  A 401 from any other route is a deleted session (› Permissions and sessions).
- Never copy query data into `useState` or context. Read it from the hook wherever
  it's needed; TanStack Query dedupes the request.
- No `useEffect` for fetching data or for deriving one value from another.

### Mutations

One hook per mutation, named `use` + the action: `useSignOut`, `useGenerateText`.
It updates or invalidates every query key the change affects in `onSuccess`, so
callers never refetch by hand. A query key names an API resource, so a hook invalidates
another feature's resource by its key, without importing from that feature.

The hook owns the cache and nothing else: it never toasts, navigates, or sets form
state. The component that calls `mutate` does those, in the second argument, because
the same mutation can need different feedback in different places. A form does the
same in its `onSubmit`, around `mutateAsync` (› Forms).

```tsx
createPersona.mutate(persona, {
  onSuccess: (personaIdentity) => {
    toast.success('Persona created')
    navigate(`/personas/${personaIdentity}`)
  },
  onError: (error) => toast.error(apiErrorMessage(error)),
})
```

### Paged lists

A paged route is read through a page query. The pattern is
`features/personas/api/user-persona-page-query.ts`.

- The params are the route's query type from the generated schema
  (`paths['/personas']['get']['parameters']['query']`), and the key is the resource path
  then the params: `['personas', params]`. Invalidating the prefix covers every page.
- `placeholderData: keepPreviousData`, so a page change keeps the old rows on screen.
- The page, search and sort live in the URL as `page`, `q`, `sort` and `dir`, read and
  written only by the route file through `useListSearchParams` from
  `lib/use-list-search-params.ts`. A changed search, sort or filter returns to page 1.
  The list component takes its rows and states as props.
- A list someone manages has `ListSearchBox` and `ListPager` from `components/`.

### Toasts

A toast confirms something the user did, or reports a failure that has nowhere better
to show. It uses `sonner`, through `toast` imported from `'sonner'`. The one
`<Toaster />` is mounted in `AppProviders`, and no other file mounts one.

- **Success:** `toast.success` after a create, save, or delete, especially when the
  page then navigates away. A short past-tense phrase: "Persona saved".
- **Error:** an error that belongs to a field shows under that field, not in a toast,
  like a 409 name clash under Name. Anything else goes to `toast.error` with
  `apiErrorMessage(error)` from `lib/api-error.ts`. The exception is generating
  text: a failed generate or resume call shows a fixed message from
  `generate-text/generate-text-error-messages.ts`, because its detail can carry
  provider internals. A 402 (the balance) and a 409 on start or resume get their
  own fixed messages there.
- **Queries don't toast.** A failed query renders an error state where its data
  would be. The one exception is the signed-out toast (› Permissions and sessions).
- **No toast for what is already on screen**, such as a dialog that closes or a list
  that updates in place with nothing else to confirm.

What the user reads is in sentence case, and a failure says what to do next. Page and nav
names are proper nouns and keep their capitals: My Personas, My Posts.

### Sign-in

Google sign-in is a full-page navigation, not a request: an `<a href>` to
`/api/auth/google/login`, built once in `GoogleSignInButton` (`components/`), with
`invite_code` when there is one. The backend redirects to Google, Google redirects to
the callback, and the callback sets the cookie and redirects back to the app. A failed
or invited sign-in lands on `/sign-in` with `error`, `invite_error` or `invite`, and
`features/auth/sign-in-result-messages.ts` turns each code into what the page says.

`POST /invites/check` is read as a query
(`features/invites/api/invite-status-query.ts`), since it changes nothing: the code
goes in the body, and `gcTime: 0` drops it with the page.

## Forms

Forms use TanStack Form, validated with a Zod schema. The app's form layer is in
`components/form/`:

- `use-app-form.ts` builds `useAppForm`, `withForm` and `withFieldGroup` with
  `createFormHook`. It registers the field components in this folder and the form
  components (`SubmitButton`).
- Each field component renders its control through `FormField`. `FormField` owns the
  label, description, error, and the ids that tie them together, so a form never
  wires those by hand.

A feature's form has three parts. `features/personas/` is the example:

- **`<entity>-form-schema.ts`**, at the feature root beside `api/` and `components/`,
  holds the Zod schema, the empty values, and the shared
  `formOptions`. The schema's limits mirror the backend DTO, with a comment naming
  it. Parsing the form values gives the request body, because the trimming and the
  blank-to-`null` transforms live in the schema.
- **`<entity>-form.tsx`** holds the fields and buttons, built with `withForm` from the
  shared options. It has no behaviour of its own.
- **One component per action**, such as `create-persona-form.tsx` and
  `edit-persona-form.tsx`. Each calls `useAppForm` with the shared options and an
  `onSubmit` that:
  - parses the values
  - awaits the mutation's `mutateAsync`, so the submit button stays disabled while
    the request runs. A submit that can take long, like generating text, gives
    `SubmitButton` a `pendingLabel` ("Writing…") and a `pendingHint` saying how long,
    rather than a hand-built button
  - then toasts and navigates

Validation:

- `validationLogic: revalidateLogic()`, with the schema as `validators.onDynamic`.
  Nothing is flagged until the first submit; after that, fields recheck as the user
  types.
- `onSubmitInvalid: focusFirstInvalidField`, so a failed submit lands on the first
  error.
- An API error about one field goes on that field, with
  `setFieldServerError(formApi, '<field>', message)`. `FormField` clears it when the
  user edits the field. Any other API error is a toast (› Toasts).

Fields reused across forms, like the blog post publishing controls, are a field group:
`withFieldGroup` from `use-app-form.ts`, defined in the feature's `components/` with
its `defaultValues`. A parent form nests the values under a key and renders
`<PublishingFields form={form} fields="publishing" isPersonaPublic={...} />`, so the
same fields serve more than one form. The group's Zod schema is exported from its own
`<group>-form-schema.ts` at the feature root, like `publishing-form-schema.ts`, and
nested into each parent's schema.

A new kind of control, such as a select or date picker, is a new field component in
`components/form/`, registered in `use-app-form.ts`. For a form shape the app doesn't
have yet, such as array fields, fields that depend on each other, or async
validation:

1. Read TanStack Form's guides first, starting from
   https://tanstack.com/form/latest/docs/framework/react/guides/basic-concepts, then
   Form Composition, Validation, Linked Fields, and Arrays.
2. Add what's reusable to `components/form/`.
3. Record the pattern here.

## Routing

The route tree lives in `app/router.tsx`. Paths are kebab-case (`/blog-posts`), like
the backend's. A section that needs sign-in is a layout route wrapped in
`<RequireAuth>`, which renders the child route, redirects when signed out, and shows
a loading state while the current user loads. A route that needs a permission is
wrapped in `<RequirePermission>` too (› Permissions and sessions). Pages don't check
auth themselves.

`AppLayout` renders `<ScrollRestoration />`, so every navigation opens at the top. A
page that changes in place scrolls to the top itself: the run page when its polled
status goes from working to paused or finished (`useRunReadyNotice`), and the write
form when it folds into its status card. When there's something new to look at, a
toast says what.

A route that needs something from the layout says so in its `handle`, typed as
`AppRouteHandle` from `app-layout.tsx`; its fields say what each does, and
`react-styling.md` › Layout covers the ones that change the layout.

## States

A view that loads data has a loading, an empty and an error state, and a not-found
state when it's read by identity. A button is disabled while its request runs. A
destructive or far-reaching action confirms first through `ConfirmActionButton`
(`components/`); its caller closes the dialog on success, so a failure leaves it open. Build the states from `CardListSkeleton` and `QueryErrorState` in
`components/`; a table uses `DataTable`, which has them built in. A list with a search tells an empty search apart from having nothing.

## Accessibility

A link navigates and a button acts. No interactive element sits inside another. Every
control has a label (an icon-only button: `react-styling.md` › Icons). Headings descend
in order. A sortable column says its sort with `aria-sort`. Colour is never the only
signal.

## Trust

Hiding or disabling a control is a courtesy, never the check: the API refuses, and the
page handles the refusal. A secret such as an invite code stays out of query keys that
outlive the page, toasts and logs. No `dangerouslySetInnerHTML`.

## Permissions and sessions

The UI checks permissions, never roles: `hasPermission(user, 'PERSONA_WRITE')` from
`features/auth/permissions.ts`. Only these check: the nav in `AppLayout`, the `auth`
feature's own components (the user menu, the balance banner), the `RequirePermission`
layout route (the pattern is `features/auth/components/require-permission.tsx`), and a
route file passing `canEdit` or the like to a feature component. `RequirePermission`
redirects when signed out and shows a no-access message when the permission is
missing. A feature other than `auth` never reads the current user; it may invalidate
`['users', 'me']` by key (› Mutations).

When the server deletes a session, the API's 401 clears its cookie. On a 401 from any
path but `/users/me` and `/auth/logout`, `lib/api-client.ts` sets `['users', 'me']` to
`null` and, if a user was signed in, toasts "You were signed out. Sign in again." once.
`app/query-client.ts` retries a query once after a 401, so an open route succeeds
signed out and a guarded one redirects. A mutation's caller skips its own failure toast
for a 401 (`isSessionEndedError(error)` from `lib/api-error.ts`), since that toast has
said it.

## Naming

| Kind                 | File                     | Name                        |
| -------------------- | ------------------------ | --------------------------- |
| Component            | `sign-in-card.tsx`       | `SignInCard`                |
| Page                 | `home-page.tsx`          | `HomePage`                  |
| Hook                 | `use-sign-out.ts`        | `useSignOut`                |
| Query                | `current-user-query.ts`  | `currentUserQueryOptions`, `useCurrentUser` |
| Props type           | same file as component   | `SignInCardProps`           |
| Module constant      | any                      | `SESSION_REFRESH_MS`        |

- Every file name is kebab-case, matching shadcn's.
- Named exports only. No `export default`, except where a tool requires it
  (`vite.config.ts`).
- Names say what the thing is without context, as in `python-naming.md`: no bare
  `data`, `item`, `info`, `helper`, `utils`. The exception is `lib/utils.ts`, which
  shadcn owns.
- Booleans start with `is`, `has`, or `can`: `isSignedIn`, `hasDraft`.
- Props are a `type`, not an `interface`, named `<Component>Props`.

## TypeScript

- No `any`. Use `unknown` and narrow it.
- No non-null `!`, except `document.getElementById('root')!` in `main.tsx`.
- Import types with `import type`, which `verbatimModuleSyntax` requires anyway.
- Import from `src/` with the `@/` alias. Use relative imports only within a
  feature's own folder.

## Comments

- A comment on a component, hook or function is one plain sentence saying what it
  does, never a paragraph, and only when its name doesn't already say it. A reason, a
  constraint or a trap goes in a comment beside the line it concerns.
- A function or component with several steps gets a short comment above each block
  saying what the block does, so its steps read from the comments alone, without
  reading the code:

```tsx
async function handleSubmit(personaFormValues: PersonaFormValues) {
  // Save the persona
  ...
  // Confirm, then go to its page
  ...
}
```

## Formatting

oxfmt formats every file, `components/ui/` included, with the settings in
`.oxfmtrc.json`: single quotes, no semicolons, 100-character lines. It also sorts
imports and Tailwind classes, including inside `cn()` and `cva()`. Don't hand-order
either, and don't fight the formatter with `// oxfmt-ignore` to keep a layout.

Run `npm run fmt` after writing and after every `npx shadcn@latest add`, since shadcn
generates double quotes. The commands, and which ones run before a commit, are in
`CLAUDE.md` › Commands.
