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

- The file sits beside its source as `<name>.test.ts`, or `.test.tsx` for one that
  renders.
- A test's name says the behaviour, not the function: "rounds half away from zero",
  not "formatUsd works".
- Import from `vitest` (`describe`, `it`, `expect`); no globals.
- No mocked API. A function that needs the API isn't a unit test's subject; leave it
  to the end-to-end flows.
- Runs in Node by default. A hook's test opts into a DOM with a
  `// @vitest-environment jsdom` comment at the top of its file, and renders the hook
  with `renderHook` from `@testing-library/react`, wrapped in what it needs (a
  `MemoryRouter` for a hook that reads the URL).
- A test proves one behaviour, and fails if that behaviour breaks: assert the exact
  value, not that something exists.

## End-to-end tests

Filled in with the Playwright setup.
