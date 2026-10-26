# OpsDesk

OpsDesk is a support-ticket application built with Python, FastAPI, PostgreSQL,
React and TypeScript. The backend uses organization membership to separate tenant
data. I am building it as a backend-focused portfolio project, with practical
full-stack learning documented in my
[bootcamp repository](https://github.com/ozdemirr1/ai-backend-bootcamp).

## Try the live preview

**[Open OpsDesk](https://opsdesk-production-448f.up.railway.app/)**

As of **25 October 2026**, registration, login, session checking and sign-out work
in the browser against the FastAPI backend and hosted PostgreSQL database.
FastAPI serves the React build and API from the same origin on Railway.

Use a made-up email such as `your-name-demo-25@example.com` and a password used
only for this demo. Accounts may be reset; do not enter real customer/support data.
Tokens stay in memory, so reloading requires login again. Sign-out clears the
browser session; it is not server-side JWT revocation.

**The Ticket dashboard is explicitly labelled mock data.** Search, status filtering
and details use three synthetic records. It is an early identity-flow preview;
real Ticket UI integration, comments, workflow actions and AI are not delivered yet.

![Live OpsDesk mock Ticket dashboard, captured 25 October 2026](docs/images/dashboard-2026-10-25.jpg)

Actual browser capture of deployed source `255f937`; no product mockup or generated
interface. The preview is a learning deployment, not a production-readiness claim.

## Implemented and planned

| Area | Implemented now | Remaining work |
| --- | --- | --- |
| Identity | Registration, Argon2id password hashes, JWT login, persisted active User resolution; browser forms/session handling | Bounded public-demo abuse controls and further operational verification |
| Organizations | Atomic creation with owner membership; membership-scoped list/detail API | Organization selection in the UI; membership/role/ownership mutations |
| Tickets | Tenant-consistent schema, creation and scoped list/detail APIs with title search/filter/pagination; mock table and detail card | Real API-to-UI integration, assignment, priority changes, status workflow, comments |
| Quality and deployment | Backend/frontend CI; guarded local PostgreSQL tests; live same-origin preview and health endpoints | PostgreSQL CI, isolated restore/rollback evidence, broader release gates |
| UI and AI | Typed components, accessible table semantics, focus handling and basic CSS | Week 16 full Month 04 UI package; AI planned for Month 06 |

The Week 16 backend now exposes nine business endpoints: `POST /users`,
`POST /auth/login`, `GET /users/me`, `POST /organizations`, `GET /organizations`,
`GET /organizations/{organization_id}` and
`POST /organizations/{organization_id}/tickets`,
`GET /organizations/{organization_id}/tickets` and
`GET /organizations/{organization_id}/tickets/{ticket_id}`, plus two health endpoints.
The new reads belong to Week 16; the last verified live preview runs the Week 15 source.
The 22-endpoint design inventory describes the target, not the implemented API.

## Verification evidence

These are separate, dated test groups, not a combined current-run total:

| Check | Last recorded local result | Date |
| --- | --- | --- |
| Frontend | 141 tests across 10 files with one worker; build and lint passed | 26 October |
| Backend non-integration | 583 passed; 181 database/schema tests deselected; Ruff passed | 26 October |
| PostgreSQL data integration | 178 passed on guarded `opsdesk_product_test` | 26 October |
| Guarded schema/migration suite | 3 passed | 5 October |

The 26 October frontend retry used one worker after an initial disk-space error;
see the [baseline and contract preparation](docs/issues/f11.md#week-16-implementation-ready-contract--26-october-2026).
Ticket reads/search are implemented and locally tested; see the
[implementation evidence](docs/issues/f11.md#week-16-local-implementation--26-october-2026).
The schema suite was not rerun for this read-only change; no migration was added.

Week 15 merged through [PR #43](https://github.com/ozdemirr1/opsdesk/pull/43).
[Backend CI](https://github.com/ozdemirr1/opsdesk/actions/runs/40193369253) and
[Frontend CI](https://github.com/ozdemirr1/opsdesk/actions/runs/40193369467)
passed at merge commit `122c052`. Backend CI excludes PostgreSQL tests.
The deployed source is `255f937`; both health endpoints returned 200 on 25 October.
Full evidence, limitations and issue closures are in [project status](docs/project-status.md).

## Run locally and explore the design

- [Backend setup, configuration, database targets and test commands](docs/development.md)
- [Frontend setup, architecture and browser checks](frontend/README.md)
- [Requirements](docs/requirements.md), [domain model](docs/domain-model.md),
  [relational model](docs/relational-model.md) and [ERD](docs/erd.md)
- [API contract](docs/api-contract.md), [access rules](docs/access-control.md),
  [Ticket lifecycle](docs/ticket-lifecycle.md) and [concurrency contract](docs/concurrency-contract.md)
- [Published backlog and original scope](docs/issue-plan.md)
- [Week 16 integration/UI plan](https://github.com/ozdemirr1/ai-backend-bootcamp/blob/main/weekly-reports/week-16-plan.md)

Local product databases are `opsdesk_product_dev` and `opsdesk_product_test`.
The older bootcamp databases `opsdesk_dev` / `opsdesk_test` are separate learning
artifacts. Never run destructive tests against development or the hosted demo.

Next: runtime response validation and authenticated
Organization context, persisted comments, a role-aware priority action and the
full Month 04 UI package. The revised Week 16 plan allocates 42 focused hours plus
up to 8 contingency hours; these are targets, not shipped features. Docker/Redis remain Month 05;
AI summarization, priority/category suggestions and evaluations remain Month 06.
The broader backend release issue R01 is still open: this smaller identity preview
does not fulfill its complete feature and operational acceptance criteria.
