---
paths:
  - "frontend/**/*.test.ts"
  - "frontend/**/*.test.tsx"
  - "frontend/e2e/**"
---

# Frontend testing

Two kinds of test, run by different tools: unit tests with Vitest for logic with no
screen, and end-to-end tests with Playwright for whole flows against the real backend.
No component tests: a component's job is markup, which the build, the reviewer and the
end-to-end flows already cover.

## Unit tests

**What gets one:** a plain function or a hook whose logic can be wrong in a way the
types don't catch, such as parsing, rounding, de-duplicating, mapping a status to a
message, or a hook that reads and writes the URL. The pattern is
`src/lib/format-usd.test.ts`.

**What doesn't:** a component, a query or mutation hook that only calls `apiClient`,
and anything the generated types or the build already prove.

- The file sits beside its source as `<name>.test.ts`, or `.test.tsx` when it holds
  JSX (a `MemoryRouter` wrapper).
- A test's name says the behaviour, not the function: "rounds half away from zero",
  not "formatUsd works".
- Import from `vitest` (`describe`, `it`, `expect`); no globals.
- No mocked API. A function that needs the API isn't a unit test's subject; leave it
  to the end-to-end flows.
- Runs in Node by default. A hook's test opts into a DOM with a
  `// @vitest-environment jsdom` comment at the top of its file, and renders the hook
  with `renderHook` from `@testing-library/react`, wrapped in what it needs (a
  `MemoryRouter` for a hook that reads the URL). `src/test-setup.ts` unmounts rendered
  hooks after each test. A hook that navigates is checked through `useLocation()` and
  `useNavigationType()` called in the same `renderHook` callback.
- A hook that waits for a frame or a timer runs under `vi.useFakeTimers()`, advanced
  inside `act`. A browser measurement (`getBoundingClientRect`, `innerHeight`) is
  stubbed with `vi.spyOn`. Every fake is restored in an `after` hook: the one matching
  the `before` that set it, or `afterEach` for one set inside a test.
- A date test pins a time zone away from UTC (`vi.stubEnv('TZ', 'Asia/Tokyo')`), so
  local time and UTC differ. The locale can't be set from a test, so `npm run test`
  runs with `LC_ALL=en_US.UTF-8`; run single files through `npm run test -- <files>`.
- A pure function a query's `select` uses may be exported from the query's file, for
  its unit test.
- An object from the schema is a full typed literal, never a partial with `as`; a local
  `build<Entity>(…)` takes only the fields the test varies.
- A test proves one behaviour, and fails if that behaviour breaks: assert the exact
  value, not that something exists.

## End-to-end tests

A flow walks the real app against the real local API and its dev seed
(`backend/scripts/dev_seed.py`), the way a person would. The pattern is
`e2e/reading-signed-out.spec.ts`.

- One file per flow in `frontend/e2e/`, named for it (`admin-users.spec.ts`).
- Sign in with the `signInAs` fixture from `e2e/fixtures.ts`, which mints a session for
  one of the seeded users and sets the `sid` cookie. Google's own screen isn't tested.
  Signing out from the UI deletes that session, which is fine: each test mints its own.
- Find elements by role and label (`getByRole`, `getByLabel`), never by class or test
  id. A selector that needs a class means the page is missing a label.
- A test reads the seeded data, and makes anything it changes itself, through the UI or
  the API (`page.request`, which carries the signed-in context's cookie). It undoes
  the change before it ends where later tests rely on the seed (a suspended user is
  reactivated), and never relies on another test's changes, so any one runs alone.
- No real generate run: a flow never reaches the model. The 402 path uses the seeded
  creator at $0.
- Local only: `e2e/global-setup.ts` stops the run unless the API on `localhost:8000`
  answers and has the seed. Flows run one at a time (`workers: 1`), since they share
  the database.
- Run with `npm run test:e2e -- <files>`; the config starts its own dev server on
  port 5181.
