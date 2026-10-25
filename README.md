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
| Tickets | Tenant-consistent schema and authenticated creation API; mock table, badges, local filters and detail card | Real list/detail API and UI, assignment, priority changes, status workflow, comments |
| Quality and deployment | Backend/frontend CI; guarded local PostgreSQL tests; live same-origin preview and health endpoints | PostgreSQL CI, isolated restore/rollback evidence, broader release gates |
| UI and AI | Typed components, accessible table semantics, focus handling and basic CSS | Week 16 bounded Tailwind/responsive pass; AI planned for Month 06 |

The backend currently exposes seven business endpoints: `POST /users`,
`POST /auth/login`, `GET /users/me`, `POST /organizations`, `GET /organizations`,
`GET /organizations/{organization_id}` and
`POST /organizations/{organization_id}/tickets`, plus two health endpoints.
The 22-endpoint design inventory describes the target, not the implemented API.

## Verification evidence

These are separate, dated test groups, not a combined current-run total:

| Check | Last recorded local result | Date |
| --- | --- | --- |
| Frontend | 141 tests across 10 files; build and lint passed | 24 October |
| Backend non-integration | 506 passed; 160 database/schema tests deselected | 19 October |
| PostgreSQL data integration | 157 passed | 5 October |
| Guarded schema/migration suite | 3 passed | 5 October |

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

Next: tenant-safe Ticket reads, runtime response validation and authenticated
Organization context, then a bounded UI pass. Docker/Redis remain Month 05;
AI summarization, priority/category suggestions and evaluations remain Month 06.
The broader backend release issue R01 is still open: this smaller identity preview
does not fulfill its complete feature and operational acceptance criteria.
