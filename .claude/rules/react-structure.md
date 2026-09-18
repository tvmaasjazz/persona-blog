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
| Styling       | Tailwind v4 with design tokens: see `react-styling.md`         |

Ask before adding a dependency, and before any global client state library
(Zustand, Redux, Jotai). Server data lives in TanStack Query and UI state in
`useState`; nothing so far has needed more.

```
frontend/src/
├── main.tsx                   # createRoot, renders <AppProviders> + <RouterProvider>
├── index.css                  # Tailwind entry and design tokens
├── app/
│   ├── providers.tsx          # AppProviders: QueryClientProvider, ...
│   ├── query-client.ts        # the one QueryClient and its defaults
│   └── router.tsx             # the route tree
├── routes/                    # one file per page, composed from features
│   ├── home-page.tsx          # HomePage
│   └── write-page.tsx         # WritePage
├── features/
│   └── auth/                  # a feature: one area of the product
│       ├── api/
│       │   ├── current-user-query.ts   # currentUserQueryOptions, useCurrentUser
│       │   └── use-sign-out.ts         # useSignOut mutation
│       ├── components/
│       │   ├── require-auth.tsx        # RequireAuth route guard
│       │   └── sign-in-button.tsx      # SignInButton
│       └── hooks/             # hooks with no API call, if the feature has any
├── components/
│   ├── ui/                    # shadcn/ui, added with the CLI, never hand-created
│   └── layout/                # app-wide shell: AppLayout, NavRail, ...
└── lib/
    ├── api-client.ts          # apiClient: the openapi-fetch instance
    ├── api-schema.gen.ts      # generated from /openapi.json, never hand-edited
    └── utils.ts               # cn(), from shadcn
```

`App.tsx` is the step 4 placeholder. Step 11 replaces it with `app/` and `routes/`.

## Features

A feature is one area of the product: `auth`, `personas`, `blog-posts`,
`generate-text`. Name it after the backend domain it talks to when there is one, in
kebab-case: backend `generate_text` is feature `generate-text`. Create only the
subfolders a feature uses.

A feature never imports from another feature. When a page needs two features, the
route file in `routes/` composes them, the way a backend lib composes two services
instead of one domain importing another. What more than one feature needs moves to
`components/` or `lib/`.

`routes/` files are thin: they lay out feature components and read route params. No
API calls and no business logic.

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
- A 401 from `/users/me` means signed out. Its query function returns `null` rather
  than throwing, so `useCurrentUser()` gives the user or `null`, never an error state.
- Never copy query data into `useState` or context. Read it from the hook wherever
  it's needed; TanStack Query dedupes the request.
- No `useEffect` for fetching data or for deriving one value from another.

### Mutations

One hook per mutation, named `use` + the action: `useSignOut`, `useGenerateText`.
It updates or invalidates every query key the change affects in `onSuccess`, so
callers never refetch by hand.

### Sign-in

Google sign-in is a full-page navigation, not a request: an `<a href>` to
`/api/auth/google/login`. The backend redirects to Google, Google redirects to the
callback, and the callback sets the cookie and redirects back to the app.

## Routing

The route tree lives in `app/router.tsx`. Paths are kebab-case (`/blog-posts`), like
the backend's. A section that needs sign-in is a layout route wrapped in
`<RequireAuth>`, which renders the child route, redirects when signed out, and shows
a loading state while the current user loads. Pages don't check auth themselves.

## Naming

| Kind                 | File                     | Name                        |
| -------------------- | ------------------------ | --------------------------- |
| Component            | `sign-in-button.tsx`     | `SignInButton`              |
| Page                 | `home-page.tsx`          | `HomePage`                  |
| Hook                 | `use-sign-out.ts`        | `useSignOut`                |
| Query                | `current-user-query.ts`  | `currentUserQueryOptions`, `useCurrentUser` |
| Props type           | same file as component   | `SignInButtonProps`         |
| Module constant      | any                      | `SESSION_REFRESH_MS`        |

- Every file name is kebab-case, matching shadcn's.
- Named exports only. No `export default`, except where a tool requires it
  (`vite.config.ts`). The step 4 `App.tsx` placeholder still has one until step 11
  replaces it.
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

No formatter is set up yet. Hand-written files use single quotes, no semicolons, and
2-space indent. Files in `components/ui/` keep the double quotes shadcn generates;
don't reformat them.

## Checks

Run from `frontend/` before proposing a commit:

```bash
npm run lint      # oxlint
npm run build     # tsc -b and vite build
```
