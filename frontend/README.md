# OpsDesk Frontend

React + TypeScript interface for the OpsDesk support-ticket product, developed
inside the product monorepo. Vite provides the development server and build tooling.

## Current scope — Week 14

Implemented: an application shell with a typed `AppHeader` and local selection
between a mock Ticket list and controlled Login/Register demos. `App` holds one typed
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

The Register demo adds a UI-only confirmation field to controlled email/password
inputs. It checks required fields and basic email shape before comparing raw
password strings. Validation errors preserve inputs; changing any field clears
stale feedback. Demo completion shows `Demo only: no account was created.`, clears
both password fields, and retains email. Leaving the screen discards form state.
Confirmation is not part of the backend registration payload, which accepts only
email/password. These demos do not implement the backend's complete validation
policy, create accounts, or establish authenticated sessions.
The API request layer is implemented separately from these demos. It returns a
discriminated result with unknown success data or an HTTP/network/invalid-response/
aborted outcome. Error envelopes receive runtime checks and known codes map to
fixed frontend messages; arbitrary server messages are not displayed. Cancellation
is handled during both fetch and body reading. Success data still needs endpoint-
specific validation before use. JSON bodies are required; 204 support and automatic
retries are outside this helper's current contract.

A real local browser probe through the Vite proxy verified a token-free GET /users/me
returns HTTP 401 and the expected safe client result. This establishes request/error
transport, not successful authentication or database connectivity. Form wiring,
sessions, protected routes, Tailwind and deployment remain later work. The demo
screens themselves still run without the backend.

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
removing the `/api` prefix. Start the backend using the product README's development
configuration, then run `npm run dev` in a second terminal. Backend environment
variables belong to its terminal; they do not automatically carry to new terminals.
The backend does not automatically load an env file. Wait for
`Application startup complete`; the reloader's startup line alone is insufficient.
Keep both development servers running for the check.

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
- Register smoke check: submit mismatched passwords, correct confirmation, and press
  Enter. Verify the explicit demo status, retained email, both passwords cleared,
  and fresh fields/feedback after leaving the screen and returning.

Vitest runs React Testing Library tests in jsdom. user-event simulates awaited user
interactions; jest-dom supplies DOM assertions. `src/test/setup.ts` cleans up each
rendered tree after its test. Three App tests cover initial selection, Login and
return to Tickets, and Register selection with other content/buttons inactive,
including removal/restoration of the named Ticket list. Two TicketList tests use
independent fixtures to verify populated row count and field association via within(),
and an empty-state message with no list/items. Seven LoginForm tests cover editable
inputs, missing email/password, malformed email, demo success with password clearing,
error clearing on email edit, and success clearing on password edit. App navigation
also verifies that Login controls appear and disappear with screen selection.
Eleven RegisterForm tests cover typing, five validation failures, mismatch correction
with Enter submission, retained email and both-password clearing, and feedback
clearing through all three field handlers. App's Register test establishes a mismatch
alert before switching screens, then verifies empty fields and absent feedback on
return. These UI cases account for twenty-three tests across four files. Nine
error-boundary tests cover runtime envelope validation and safe message selection;
nine request-client tests cover URL/options forwarding, success, HTTP errors,
non-JSON bodies, network rejection and cancellation before/during body reading.
Global fetch stubs are restored after each client test. In total, forty-one tests
across six files pass locally. Mocked tests do not establish real proxy behavior;
the separate local browser check above supplies that evidence.
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
- `src/components/RegisterForm.tsx`: controlled Register demo with UI-only confirmation.
- `src/components/RegisterForm.test.tsx`: validation, correction, and feedback tests.
- `src/types/ticket.ts`: Ticket status, priority, and summary types.
- `src/data/mockTickets.ts`: synthetic display data passed to the list by App.
- `src/index.css`: global typography, colors, and box sizing.
- `src/App.css`: application spacing and layout.

Keep `package-lock.json` under version control. `node_modules/` and `dist/` are
ignored generated directories. Never place backend secrets in frontend source or
browser-exposed configuration, and never log, render, persist, or commit passwords
or complete access tokens.

See the [product README](../README.md) for backend capabilities and setup.
