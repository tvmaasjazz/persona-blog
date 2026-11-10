# Persona Blog frontend

React + Vite + TypeScript, styled with Tailwind and shadcn/ui. Conventions are in
`.claude/rules/react-structure.md`, `react-styling.md` and `react-testing.md`.

Run from `frontend/`:

```bash
npm install       # install dependencies
npm run dev       # dev server at http://localhost:5173
npm run build     # type-check and build to dist/
npm run test      # Vitest unit tests
npm run test:e2e  # Playwright flows (needs the API on port 8000 and the dev seed)
npm run fmt       # format with oxfmt
npm run fmt:check # check formatting without writing
npm run lint      # oxlint
npm run api:types # regenerate src/lib/api-schema.gen.ts (needs the API on port 8000)
npx shadcn@latest add <component>   # add a shadcn/ui component to src/components/ui/
```
