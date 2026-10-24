# OpsDesk Frontend

React + TypeScript interface for the OpsDesk support-ticket product, developed
inside the product monorepo. Vite provides the development server and build tooling.

## Current scope — Week 15

Implemented: an application shell with a typed `AppHeader` and local selection
between a mock Ticket list and real API registration/login. `App` owns typed screen
selection and a separate in-memory session. Button handlers select a screen and
conditional rendering displays its content. Buttons expose selection through `aria-pressed` and include visible
keyboard focus. Screen selection is local navigation; a full reload resets both
selection and the in-memory session.

TicketTable receives typed summaries through props and renders three synthetic
records with stable ticketId keys. Its caption, column headers and row headers
identify ID, title, status and priority. An empty array displays `No tickets yet.`
without a table. StatusBadge maps all four TicketStatus values to readable labels;
color is supplementary. The table container supports keyboard focus and horizontal
scrolling on narrow screens. Neither component owns state or calls an API.
TicketSummary remains a frontend display model, not the backend response contract.
TicketDashboard owns title search and status selection, deriving matching rows
from its typed tickets prop. Title matching ignores case and surrounding query
whitespace while preserving the entered text. A checked value guard accepts only
listed statuses or All statuses. Both conditions apply together; Clear filters
resets them. The labelled controls wrap on narrow screens and have visible keyboard
focus. A visible count shows matching and total tickets. A nonempty source with no
matches shows `No matching tickets.`; an empty source retains `No tickets yet.`.
Leaving Tickets unmounts the dashboard and resets both controls on return; App
continues to own the session. Selecting a ticket highlights its row and opens a
bounded fixture detail card below the still-visible table with ID, title, status,
priority and optional description. Close details preserves the current search
and status selection, while leaving Tickets resets selection and filters. Native
buttons support keyboard activation; focus moves to Close details on opening,
then returns to the selected row on closing. Changing filters closes the card.
This is local conditional rendering, not a URL route. Comments and real Ticket API
integration remain pending.
The identity preview is hosted on Railway. The table increment was pushed as
`30e5d03`; its deployment was blocked by a provider pause on 21 October. The title
search increment was pushed as `3a5b11b`; publication of the newer status-filter
increment has not been verified.

Login sends `POST /auth/login` with explicit email/password input. The adapter
requires HTTP 200 and a runtime-checked nonempty bearer token, then the form calls
`GET /users/me` with that token. Authenticated UI requires HTTP 200, a checked public
profile and `is_active: true`. A token-shaped response alone does not establish a
verified session. Login uses bounded email validation and NFC-normalized passwords
of 15–128 Unicode code points; passwords are not trimmed, logged or persisted.

Controls stay disabled across both requests. An immediate request ref prevents
repeated submission, the same AbortSignal reaches both requests, and ownership checks
ignore stale results after unmount. Aborted outcomes do not show an error. Retrying
clears old feedback before waiting; a login 401 shows `Email or password is incorrect.`
The password clears after successful token retrieval. Only a checked active profile
allows the token/profile pair to enter App state and replace the form with signed-in
feedback. Screen changes preserve that session; a full reload clears it. No browser
storage or refresh tokens are used.

Sign out is available across screens while authenticated. It clears the session,
cancels a pending check and opens an empty Login form without an API logout call.
It does not revoke an already issued JWT. Check session explicitly calls /users/me:
a checked active profile updates the displayed user; HTTP 401 or an inactive profile
clears the session and shows `Your session is no longer valid. Please sign in again.`
Network, HTTP 500 and malformed responses preserve the session and show a fixed
retry message. Aborted outcomes are silent. The check button is disabled while
pending, but Sign out stays available. Request ownership, abort and current-token
checks prevent stale results from changing a cleared or replaced session. App unmount
also cancels the check. Successful login clears the old session warning. There is no
automatic expiry timer; invalidity is discovered when the protected check is made.

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
passwords. Registration does not automatically start a session; the separate Login
flow handles authentication. Editing a field clears feedback. Known HTTP errors use fixed frontend messages, including the duplicate
email message; arbitrary server messages are not displayed.

The shared request helper distinguishes HTTP, network, invalid-response and aborted
outcomes, including cancellation during body reading. Success data is unknown until
an endpoint adapter validates it. JSON bodies are required; 204 support is outside
this helper's current contract.

Local Safari checks on 15 October showed registration success and duplicate-email
feedback; backend logs confirmed HTTP 201 and 409. On 16 October, browser checks and
backend logs demonstrated failed login (401), creation of a fresh synthetic account
(201), successful login (200) and current-user retrieval (200). All supplied request
logs reported `unexpected_error: false`. Signed-in feedback survived Tickets → Login
navigation without another login request; a full reload restored the empty Login form.
These checks establish local integration. Tickets remain explicitly labelled mock
data; protected routes, Tailwind and hosted deployment remain later work.

On 17 October, Safari/backend evidence showed a valid session check returning 200.
Changing the local development signing secret and restarting the backend while keeping
the browser session produced /users/me 401, removed session controls and displayed the
Login form with the expected warning. Subsequent login and profile requests returned
200 and the warning disappeared. This tests invalid signatures, not time-based expiry.
Explicit Sign out/navigation behavior is covered by component tests and learner
manual confirmation: Sign out opened an empty Login form, Tickets displayed three
mock records, and returning to Login kept the inputs empty without restoring a session.

## 21 October title-search verification

Node.js 24 checks passed 123 frontend tests across nine files, TypeScript/Vite
build, ESLint and whitespace checks. Six TicketDashboard cases cover initial rows,
case/whitespace/substring matching, clearing, no matches, empty source and changed
props. A new App test verifies search reset after Login → Tickets navigation and
preserves the mock-data notice. Existing identity/session tests also passed.
Learner-provided Chrome screenshots confirmed case-insensitive matches, a no-match message and clearing back to all three mock rows. A later screenshot confirmed the revised search-field spacing and layout on desktop. These local checks do not establish public deployment.

## 21 October status-filter verification

The status filter and search combine over the labelled mock collection. Node.js 24
checks passed 129 frontend tests across nine files, TypeScript/Vite build, ESLint
and whitespace checks. New cases cover each status, search plus status, no matches,
Clear filters, empty source and navigation reset. A local browser check confirmed
`email` plus Open gives zero matches and Clear filters restores all three rows.
These checks do not establish a public release.

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
removing the `/api` prefix; `/api/users` and `/api/auth/login` similarly forward to
`/users` and `/auth/login`. Complete
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
  rows and their fields, no key warnings, and readable narrow-screen table scrolling.
- Login smoke check with both development servers running: use a synthetic account.
  Wrong credentials that pass form validation should return 401 with the fixed login
  message and no current-user request. Correct credentials should produce login 200,
  then current-user 200 and signed-in feedback. Switch Tickets → Login: the session
  should remain without another login. Reload: the Login form should return empty.
  Record status codes and public profile/UI evidence only; never share the login
  response body, Authorization header or screenshots containing complete tokens.
- Session smoke check: while signed in, Check session should return 200 and retain
  the profile. Sign out from Tickets should open an empty Login form; navigating away
  and back must not restore the session. Sign in again. In local development only,
  restart the backend with a newly generated signing secret without refreshing the
  browser. Check session should return 401 and clear the session. Sign in again and
  verify login/profile 200 plus removal of the warning. Do not change a shared or
  production signing key for this check; do not record tokens or signing secrets.
- Register smoke check with both development servers running: use a fresh synthetic
  email and a test-only password meeting the policy. Submit and inspect Network for
  POST /api/users, HTTP 201 and the public profile. Confirm the success message,
  retained email and cleared password fields. Submit the same email again: expect
  HTTP 409, error.code=email_already_exists and the matching alert. Do not share
  request bodies containing passwords. Leaving/returning should reset form state.

Vitest runs React Testing Library tests in jsdom with awaited user-event interactions
and jest-dom assertions. `src/test/setup.ts` cleans up rendered trees after each test.
The previous local baseline had 110 passing tests across seven files: App (16), TicketList (2),
LoginForm (16), RegisterForm (25), API errors (9), request client (9), identity (33).
Registration tests cover validation boundaries and Unicode normalization, pending
controls/duplicate prevention, verified success, HTTP/uncertain outcomes, recovery,
Enter submission, feedback clearing and cancellation/stale results. Identity tests
cover runtime profiles/tokens, exact statuses, payload filtering, bearer headers and
propagated network/abort failures. Login tests cover the complete two-request pending
interval, inactive profiles, retry feedback, silent cancellation and late results.
App tests cover navigation, reload/reset, explicit logout/re-login, active profile
updates, 401/inactive cleanup, network/500/invalid-response preservation, silent aborts,
cancellation on logout/unmount, late 200 after logout and late 401 after a new login.
Async completion assertions await React updates; identity mocks reset per test.

On 20 October, after the TicketTable/StatusBadge increment, Node.js 24.21.0
verification passed 116 tests across eight files: App (16), TicketTable (3),
StatusBadge (5), LoginForm (16), RegisterForm (25), API errors (9), request client
(9), identity (33). TypeScript/Vite build, ESLint and `git diff --check` also passed.
New tests cover table headers and row associations, empty/changed props and all
four status labels. A supplied desktop screenshot shows the table and badges.
Manual confirmation covers narrow-screen scrolling, keyboard focus and Login →
Tickets navigation. These browser observations are separate from jsdom results.
Deployment of this increment is verified separately after publication.

Mocks do not prove real database access; the separate browser check supplies local
integration evidence. Build, lint and whitespace checks passed with connected login
and registration; hosted CI must still be checked after publication.
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
- `src/App.tsx`: composes the page, supplies header props, and owns screen selection plus the in-memory session.
- `src/App.test.tsx`: screen-selection and session lifecycle behavior tests.
- `src/test/setup.ts`: DOM matchers and per-test cleanup.
- `vite.config.ts`: React plugin, local API proxy and jsdom test configuration.
- `.env.example`: public API prefix example, without secrets.
- `src/api/config.ts`: browser-exposed API base configuration.
- `src/api/errors.ts` and its tests: runtime error guards and safe message mapping.
- `src/api/client.ts` and its tests: JSON requests and explicit error/cancellation outcomes.
- `src/components/AppHeader.tsx`: typed, presentational header component.
- `src/components/TicketDashboard.tsx`: local filters, selected ticket ID and derived rows.
- `src/components/TicketDashboard.test.tsx`: filtering, detail and return behavior.
- `src/components/TicketTable.tsx`: semantic table and empty state from typed props.
- `src/components/TicketTable.test.tsx`: headers, row data and changed/empty props.
- `src/components/TicketDetail.tsx`: fixture detail view and return action.
- `src/components/StatusBadge.tsx`: readable labels for the four Ticket statuses.
- `src/components/StatusBadge.test.tsx`: status labels and prop changes.
- `src/components/LoginForm.tsx`: controlled login/current-user flow, validation and cancellation.
- `src/components/LoginForm.test.tsx`: isolated form interaction tests.
- `src/components/RegisterForm.tsx`: real registration, pending/error/success and cancellation.
- `src/components/RegisterForm.test.tsx`: validation, correction, and feedback tests.
- `src/api/identity.ts` and its tests: registration/login/current-user adapters and runtime response guards.
- `src/types/user.ts`: public UserProfile contract.
- `src/types/session.ts`: in-memory token and checked UserProfile pair.
- `src/types/ticket.ts`: Ticket status, priority, and summary types.
- `src/data/mockTickets.ts`: synthetic display data passed to the table by App.
- `src/index.css`: global typography, colors, and box sizing.
- `src/App.css`: application spacing and layout.

Keep `package-lock.json` under version control. `node_modules/` and `dist/` are
ignored generated directories. Never place backend secrets in frontend source or
browser-exposed configuration, and never log, render, persist, or commit passwords
or complete access tokens.

See the [product README](../README.md) for backend capabilities and setup.


## Session and dashboard reset coverage

The labelled mock Ticket dashboard remains available without signing in.
Sign out, a session-check 401, or an inactive current User returns to Login
and removes the dashboard. Returning to Tickets starts with empty search,
all statuses and no selected detail; session controls remain absent.
App regression tests exercise all three paths with filters and an open detail.
This is a public fixture preview, not authorization for real Ticket data.
The real list/detail implementation preparation is recorded in
[F11](../docs/issues/f11.md).


## Ticket response adapter — 24 October 2026

`src/api/tickets.ts` declares the backend TicketResponse wire shape and exposes
`toTicketSummary` for the table/detail display model. It explicitly projects
display fields, preserves descriptions and returns a new object without changing
the response. Tests cover the projection, empty/multiline descriptions and source
immutability. Run them with `npm test -- src/api/tickets.test.ts`.

This module does not fetch or validate JSON. The dashboard still uses labelled
mock Tickets. Runtime response validation (including safe integer IDs), real
Ticket reads and Organization selection are integration prerequisites documented
in [F11](../docs/issues/f11.md#week-15-implementation-breakdown--24-october-2026).
