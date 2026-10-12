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
│       │   └── sign-in-card.tsx        # SignInCard
│       ├── hooks/             # hooks with no API call, if the feature has any
│       └── <what-it-holds>.ts # plain helpers for this feature only, like run-steps.ts
├── components/
│   ├── ui/                    # shadcn/ui, added with the CLI, never hand-created
│   ├── form/                  # the form layer: useAppForm, field components
│   └── layout/                # app-wide shell: AppLayout
└── lib/
    ├── api-client.ts          # apiClient: the openapi-fetch instance
    ├── api-error.ts           # ApiError, createApiError, apiErrorMessage
    ├── api-schema.gen.ts      # generated from /openapi.json, never hand-edited
    └── utils.ts               # cn(), from shadcn
```

## Features

A feature is one area of the product: `auth`, `personas`, `blog-posts`,
`generate-text`. Name it after the backend domain it talks to when there is one, in
kebab-case: backend `generate_text` is feature `generate-text`. Create only the
subfolders a feature uses.

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
reads `usePersonaList()` and hands the personas to the generate form.

No barrel `index.ts` files. Import from the file that defines the thing.

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
hand-written interface that mirrors a backend DTO. When the backend changes, run
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
- Never copy query data into `useState` or context. Read it from the hook wherever
  it's needed; TanStack Query dedupes the request.
- No `useEffect` for fetching data or for deriving one value from another.

### Mutations

One hook per mutation, named `use` + the action: `useSignOut`, `useGenerateText`.
It updates or invalidates every query key the change affects in `onSuccess`, so
callers never refetch by hand.

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

### Toasts

A toast confirms something the user did, or reports a failure that has nowhere better
to show. It uses `sonner`, through `toast` imported from `'sonner'`. The one
`<Toaster />` is mounted in `AppProviders`, and no other file mounts one.

- **Success:** `toast.success` after a create, save, or delete, especially when the
  page then navigates away. A short past-tense phrase: "Persona saved".
- **Error:** an error that belongs to a field shows under that field, not in a toast,
  like a 409 name clash under Name. Anything else goes to `toast.error` with
  `apiErrorMessage(error)` from `lib/api-error.ts`. The exception is generating
  text: a failed generate or resume call shows a fixed message, such as "Couldn't
  write the post. Try again.", because its detail can carry provider internals.
- **Queries don't toast.** A failed query renders an error state where its data
  would be.
- **No toast for what is already on screen**, such as a dialog that closes or a list
  that updates in place with nothing else to confirm.

### Sign-in

Google sign-in is a full-page navigation, not a request: an `<a href>` to
`/api/auth/google/login`. The backend redirects to Google, Google redirects to the
callback, and the callback sets the cookie and redirects back to the app.

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
a loading state while the current user loads. Pages don't check auth themselves.

`AppLayout` renders `<ScrollRestoration />`, so every navigation opens at the top. A
page that changes in place scrolls to the top itself: the run page when a new step
comes back, and the write form when it folds into its status card. When there's
something new to look at, a toast says what.

A route that needs something from the layout says so in its `handle`, typed as
`AppRouteHandle` from `app-layout.tsx`. `hasSidebar` is the one field so far; see
`react-styling.md` › Layout for what it does.

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

## Formatting

oxfmt formats every file, `components/ui/` included, with the settings in
`.oxfmtrc.json`: single quotes, no semicolons, 100-character lines. It also sorts
imports and Tailwind classes, including inside `cn()` and `cva()`. Don't hand-order
either, and don't fight the formatter with `// oxfmt-ignore` to keep a layout.

Run `npm run fmt` after writing and after every `npx shadcn@latest add`, since shadcn
generates double quotes. The commands, and which ones run before a commit, are in
`CLAUDE.md` › Commands.
