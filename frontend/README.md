# OpsDesk Frontend

React + TypeScript interface for the OpsDesk support-ticket product, developed
inside the product monorepo. Vite provides the development server and build tooling.

## Current scope — Week 14

Implemented: an application shell with a typed `AppHeader` and local selection
between a mock Ticket list, a controlled Login demo and real API registration. `App` holds one typed
screen state, button handlers select the screen, and conditional rendering displays only
its content. Buttons expose selection through `aria-pressed` and include visible
keyboard focus. Selection resets on a full page reload; it is not routing or login.

The Ticket list receives typed summaries through props, renders three synthetic
records with stable ticketId keys, and supports an explicit empty state. Each row
shows its title, ID, status, and priority. TicketSummary is a frontend display model,
not the complete backend response contract. Ticket details wrap on narrow screens;
the unmarked list retains an explicit list role for Safari accessibility.

The Login demo owns controlled email/password inputs and transient feedback. Submit
checks required email, a basic email shape, then a non-empty password. These bounded
UX checks do not implement the backend's complete validation contract or authenticate
a User. Invalid input shows an alert; editing either field clears stale feedback.
Valid demo input shows `Demo only: no sign-in request was sent.`, clears the password,
and retains email. Passwords are not trimmed, echoed, logged, or persisted. Leaving
the Login screen unmounts the form and discards its local state.

Registration sends `POST /users` through the local proxy. The form owns email,
password and UI-only confirmation. It trims email, checks bounded ASCII/email input,
normalizes passwords to NFC and checks 15–128 Unicode code points and matching
confirmation. These UX checks complement server validation; the server remains
responsible for acceptance and uniqueness. Only email and password enter the request.

`registerUser` accepts success only for HTTP 201 with a runtime-checked UserProfile:
a positive safe integer user_id, nonempty email and boolean is_active. Invalid data
is not cast into a trusted profile. A malformed or lost response can follow a committed
account, so network/invalid-response feedback says creation could not be confirmed;
it does not automatically retry or claim that no account exists.

While pending, controls are disabled and an immediate request guard prevents duplicate
submissions. Leaving the screen aborts the request; stale results cannot update a new
form. Aborting the browser request does not guarantee a server-side rollback. Success
shows `Account created. You are not signed in.`, preserves email and clears both
passwords. No automatic login, token storage or session is implemented. Editing a field
clears feedback. Known HTTP errors use fixed frontend messages, including the duplicate
email message; arbitrary server messages are not displayed.

The shared request helper distinguishes HTTP, network, invalid-response and aborted
outcomes, including cancellation during body reading. Success data is unknown until
an endpoint adapter validates it. JSON bodies are required; 204 support is outside
this helper's current contract.

Local Safari checks on 15 October showed the returned public profile, success message
and cleared password fields, followed by `email_already_exists` and the matching UI
message on repeat submission. The screenshots show response bodies rather than HTTP
status headers. The success adapter requires 201; the duplicate-email contract is 409.
This verifies local registration behavior. Login and Tickets remain demos; sessions,
protected routes, Tailwind and hosted deployment remain later work.

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
versions. Frontend CI uses Node.js 24 LTS, compatible with the current locked tools;
use Node.js 24 for an aligned local environment. The initial Node.js 25 setup is
historical and that release line is now EOL. A local run on a different Node version
does not establish Node.js 24 compatibility; inspect the hosted result. Local
Node.js 24.21.0/npm 11.19.0 were also verified on 13 October with clean installation,
tests, build and lint.
The current lockfile resolves
React/React DOM 19.3.0, TypeScript 6.0.3, and Vite 8.3.3. Version ranges in
`package.json` may differ from exact resolved versions. Check the
[Vite guide](https://vite.dev/guide/) for runtime requirements when changing tooling.

## Local API configuration and proxy

From `frontend/`, copy the committed public example once:

```bash
cp .env.example .env.local
```

`VITE_API_BASE_URL=/api` is the default public API prefix. `src/api/config.ts` also
falls back to `/api` when the value is absent or empty. Vite exposes `VITE_` values
to browser code: never put database credentials or JWT signing secrets there.
`.env.local` is ignored; `.env.example` is committed. Restart Vite after changes.

The development proxy forwards `/api/users/me` to `http://127.0.0.1:8000/users/me`,
removing the `/api` prefix; `/api/users` similarly forwards to `/users`. Complete
the product README's development database migrations before testing registration.
Start the backend using its development configuration, then run `npm run dev` in a second terminal. Backend environment
variables belong to its terminal; they do not automatically carry to new terminals.
The backend does not automatically load an env file. Wait for
`Application startup complete`; the reloader's startup line alone is insufficient.
Keep both development servers running for the check. Startup alone does not prove
the database schema is ready.

In the browser console on the Vite development page, run:

```js
import('/src/api/client.ts')
  .then(({ requestJson }) => requestJson('/users/me'))
  .then((result) => console.log(result))
  .catch((error) => console.error(error));
```

Expected: `ok: false`, `kind: "http"`, `status: 401`, and
`Authentication failed. Please sign in again.` The Network panel shows
`/api/users/me` with HTTP 401; backend logs show `/users/me` with status 401 and
`unexpected_error: false`. A red 401 resource entry is expected for this probe.
This probe sends no credentials and creates no data. Do not log successful login
responses or tokens. The module import is a development-only check, not a built-
bundle or deployment procedure. Production origin/proxy configuration and hosted
browser verification remain separate work.

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
  visible. Use Tab and Enter/Space to operate the buttons. Confirm all three Ticket
  rows and their fields, no key warnings, and readable narrow-screen wrapping.
- Login smoke check: submit empty and malformed input, correct it, and submit via
  both button and Enter. Verify alert/status feedback, retained email, cleared
  password, and disappearance of stale feedback after editing. Use synthetic values.
- Register smoke check with both development servers running: use a fresh synthetic
  email and a test-only password meeting the policy. Submit and inspect Network for
  POST /api/users, HTTP 201 and the public profile. Confirm the success message,
  retained email and cleared password fields. Submit the same email again: expect
  HTTP 409, error.code=email_already_exists and the matching alert. Do not share
  request bodies containing passwords. Leaving/returning should reset form state.

Vitest runs React Testing Library tests in jsdom with awaited user-event interactions
and jest-dom assertions. `src/test/setup.ts` cleans up rendered trees after each test.
The local suite has 68 passing tests across seven files: App (3), TicketList (2),
LoginForm (7), RegisterForm (25), API errors (9), request client (9), identity (13).
Registration tests cover validation boundaries and Unicode normalization, pending
controls/duplicate prevention, verified success, HTTP/uncertain outcomes, recovery,
Enter submission, feedback clearing and cancellation/stale results. Identity tests
cover runtime profiles, exact status, payload filtering and propagated failures.
Mocks do not prove real database access; the separate browser check supplies local
integration evidence. Build and lint passed with the connected registration form.
Tests query accessible roles and names rather than inspecting component state.
jsdom does not establish visual layout correctness; retain browser smoke checks.
## Continuous integration

`.github/workflows/frontend-ci.yml` defines `Frontend CI` for pushes and pull requests.
One Ubuntu job uses Node.js 24, installs with `npm ci`, and runs tests, build, and
lint as separate steps inside `frontend/`. Any failed step fails the job. The job
has a ten-minute timeout and read-only repository-content permissions; checkout
does not retain Git credentials. No backend service, database, or secret is required.

setup-node caches npm package data using `frontend/package-lock.json` as the cache
dependency path. It does not cache `node_modules`; `npm ci` is still required after
a cache hit. `defaults.run.working-directory` applies to shell steps, while the
action's lockfile input is relative to the repository root.

Inspect Frontend CI at the actual pushed commit in GitHub Actions. A workflow file
or passing local checks alone do not establish hosted success. Existing Backend CI
is independent; neither job proves real API integration, visual layout, or deployment.

## Source layout

- `index.html`: document title, language, and React mount element.
- `src/main.tsx`: React entry point and global stylesheet import.
- `src/App.tsx`: composes the page, supplies header props, and owns screen selection.
- `src/App.test.tsx`: user-visible screen-selection behavior tests.
- `src/test/setup.ts`: DOM matchers and per-test cleanup.
- `vite.config.ts`: React plugin, local API proxy and jsdom test configuration.
- `.env.example`: public API prefix example, without secrets.
- `src/api/config.ts`: browser-exposed API base configuration.
- `src/api/errors.ts` and its tests: runtime error guards and safe message mapping.
- `src/api/client.ts` and its tests: JSON requests and explicit error/cancellation outcomes.
- `src/components/AppHeader.tsx`: typed, presentational header component.
- `src/components/TicketList.tsx`: props-driven populated/empty Ticket rendering.
- `src/components/TicketList.test.tsx`: isolated list behavior tests.
- `src/components/LoginForm.tsx`: controlled local Login demo and validation feedback.
- `src/components/LoginForm.test.tsx`: isolated form interaction tests.
- `src/components/RegisterForm.tsx`: real registration, pending/error/success and cancellation.
- `src/components/RegisterForm.test.tsx`: validation, correction, and feedback tests.
- `src/api/identity.ts` and its tests: registration payload and runtime profile validation.
- `src/types/user.ts`: public UserProfile contract.
- `src/types/ticket.ts`: Ticket status, priority, and summary types.
- `src/data/mockTickets.ts`: synthetic display data passed to the list by App.
- `src/index.css`: global typography, colors, and box sizing.
- `src/App.css`: application spacing and layout.

Keep `package-lock.json` under version control. `node_modules/` and `dist/` are
ignored generated directories. Never place backend secrets in frontend source or
browser-exposed configuration, and never log, render, persist, or commit passwords
or complete access tokens.

See the [product README](../README.md) for backend capabilities and setup.
