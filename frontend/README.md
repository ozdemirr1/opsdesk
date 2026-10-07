# OpsDesk Frontend

React + TypeScript interface for the OpsDesk support-ticket product, developed
inside the product monorepo. Vite provides the development server and build tooling.

## Current scope — Week 13

Implemented: an application shell with a typed `AppHeader` and local selection
between Tickets, Login, and Register placeholders. `App` holds one typed screen
state, button handlers select the screen, and conditional rendering displays only
its content. Buttons expose selection through `aria-pressed` and include visible
keyboard focus. Selection resets on a full page reload; it is not routing or login.

Planned this week: a synthetic Ticket list and controlled login/register demo forms
with behavior tests. Those list/form features are not implemented yet.
Real API calls, token storage, protected routes, Tailwind, and deployment are later
work. The current shell needs no backend, database, environment variables, or secrets.

## Setup and development

Run these commands from the repository root with Node.js and npm installed:

```bash
cd frontend
npm ci
npm run dev
```

Use the local URL printed by Vite. Stop the server with Ctrl+C. `npm ci` installs
the dependency versions recorded in `package-lock.json`; use `npm install` when
intentionally updating dependencies and review the lockfile change.

The initial setup used Node.js 25.2.1 and npm 11.6.2. These are recorded setup
versions, not a pinned or long-term runtime policy. The current lockfile resolves
React/React DOM 19.3.0, TypeScript 6.0.3, and Vite 8.3.3. Version ranges in
`package.json` may differ from exact resolved versions. Check the
[Vite guide](https://vite.dev/guide/) for runtime requirements when changing tooling.

## Checks and local build preview

From `frontend/`:

```bash
npm test
npm run build
npm run lint
```

- `test` runs Vitest once; `npm run test:watch` reruns tests while developing.
- `build` runs `tsc -b` for TypeScript checking, then `vite build` to generate `dist/`.
- `lint` runs ESLint. It does not replace type checking or browser verification.
- After building, `npm run preview` serves the generated bundle for local inspection;
  it is not a production deployment command.
- Browser smoke check: confirm the OpsDesk heading, subtitle, mock-data explanation,
  readable layout, and absence of console errors. Switch between all three screens;
  check that old content disappears, selected state changes, and keyboard focus is
  visible. Use Tab and Enter/Space to operate the buttons.

Vitest runs React Testing Library tests in jsdom. user-event simulates awaited user
interactions; jest-dom supplies DOM assertions. `src/test/setup.ts` cleans up each
rendered tree after its test. Three App tests cover initial selection, Login and
return to Tickets, and Register selection with other content/buttons inactive.
Tests query accessible roles and names rather than inspecting component state.
jsdom does not establish visual layout correctness; retain browser smoke checks.
Future forms and Ticket lists require their own behavior tests.
The repository's existing Backend CI does not run these frontend checks yet.

## Source layout

- `index.html`: document title, language, and React mount element.
- `src/main.tsx`: React entry point and global stylesheet import.
- `src/App.tsx`: composes the page, supplies header props, and owns screen selection.
- `src/App.test.tsx`: user-visible screen-selection behavior tests.
- `src/test/setup.ts`: DOM matchers and per-test cleanup.
- `vite.config.ts`: React plugin and jsdom test configuration.
- `src/components/AppHeader.tsx`: typed, presentational header component.
- `src/index.css`: global typography, colors, and box sizing.
- `src/App.css`: application spacing and layout.

Keep `package-lock.json` under version control. `node_modules/` and `dist/` are
ignored generated directories. Never place backend secrets in frontend source or
browser-exposed configuration, and never log, render, persist, or commit passwords
or complete access tokens.

See the [product README](../README.md) for backend capabilities and setup.
