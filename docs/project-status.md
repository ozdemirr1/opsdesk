# Project status — 26 October 2026

This is a dated implementation checkpoint. The [README](../README.md) summarizes
the product; contract documents describe intended rules. Issue files preserve
initial scope and dated implementation notes. GitHub remains the live work tracker.

## Delivered product boundary

- FastAPI application/configuration, safe error envelopes and request diagnostics;
  synchronous SQLAlchemy Sessions and explicit transaction ownership.
- Alembic schema for Users, Organizations, OrganizationMemberships and Tickets;
  head `31be9023cfb2`. Comments and Attachments are not migrated tables.
- Registration, login and active persisted current-User resolution.
- Atomic Organization creation and membership-scoped Organization list/detail.
- Authenticated Ticket creation with server-derived requester/creator, tenant
  constraints, ordered locks, rollback and contention tests.
- Local Week 16 scoped Ticket list/detail API with title search, filters and
  same-statement count/page/access checks; unit/API and PostgreSQL tests pass.
  These GET routes have not been deployed by this task.
- React identity forms with runtime response guards and in-memory session state.
- Public mock Ticket table, title/status filters, counts, detail card and focus
  return; session termination resets dashboard state. No Ticket HTTP reads yet.
- Pure Ticket display adapter with four tests. It neither validates unknown JSON
  nor fetches records. API types alone are not runtime validation.

## Closed design and implementation issues

GitHub state and merge evidence checked on 25 October. A closed design issue does
not mean all features governed by that design have been implemented.

| Scope | Closed issues | Merge evidence |
| --- | --- | --- |
| Ticket validation/identity design, app foundation, fast CI | #1, #2, #5, #9 | [PR #28](https://github.com/ozdemirr1/opsdesk/pull/28), `64b14eb` |
| Database lifecycle and guarded tests | #6 | [PR #29](https://github.com/ozdemirr1/opsdesk/pull/29), `3f85571` |
| Identity/Organization schema | #7 | [PR #30](https://github.com/ozdemirr1/opsdesk/pull/30), `d5147fe` |
| Shared API errors/logging | #10 | [PR #31](https://github.com/ozdemirr1/opsdesk/pull/31), `c07a48f` |
| Concurrency design | #4 | [PR #32](https://github.com/ozdemirr1/opsdesk/pull/32), `9bf8726` |
| Registration | #11 | [PR #33](https://github.com/ozdemirr1/opsdesk/pull/33), `4d8a9f1` |
| Login | #12 | [PR #34](https://github.com/ozdemirr1/opsdesk/pull/34), `d321e14` |
| Final API contracts | #3 | [PR #35](https://github.com/ozdemirr1/opsdesk/pull/35), `03f689c` |
| Current User | #13 | [PR #36](https://github.com/ozdemirr1/opsdesk/pull/36), `1641bc2` |
| Ticket schema | #8 | [PR #37](https://github.com/ozdemirr1/opsdesk/pull/37), `5151c29` |
| Organization creation | #14 | [PR #38](https://github.com/ozdemirr1/opsdesk/pull/38), `57ae5f1` |
| Organization reads | #15 | [PR #39](https://github.com/ozdemirr1/opsdesk/pull/39), `3355928` |
| Ticket creation | #18 | [PR #40](https://github.com/ozdemirr1/opsdesk/pull/40), `ec418f9` |

Frontend foundations merged in [PR #41](https://github.com/ozdemirr1/opsdesk/pull/41)
(`511715d`, historical squash). Identity integration merged normally in
[PR #42](https://github.com/ozdemirr1/opsdesk/pull/42) (`b0e6cab`). Week 15 preview,
dashboard and display adapter merged normally in
[PR #43](https://github.com/ozdemirr1/opsdesk/pull/43) (`122c052`).

## Open scope and dependencies

| Work | Issue(s) | Next decision / prerequisite |
| --- | --- | --- |
| Ticket list/detail | [F11 #19](https://github.com/ozdemirr1/opsdesk/issues/19) | Local backend implemented/tested; review/publication/CI, hosted collation check, then runtime guards and UI |
| Membership directory/add/reactivation | #16, #17 | Needed before meaningful membership administration UI; estimate at Month 04 handoff |
| Priority/assignment and status workflow | #20, #21 | Current-state role checks and cooperating locks; not inert UI buttons |
| Role/deactivation and ownership transfer | #22, #23 | Reviewed invariants and overlapping-operation tests |
| Comments | [F14 #24](https://github.com/ozdemirr1/opsdesk/issues/24) | Comment schema, read/write authorization, service/API tests before form integration |
| PostgreSQL CI | [Q03 #25](https://github.com/ozdemirr1/opsdesk/issues/25) | Dedicated isolated CI database; local passing results do not close this |
| Full backend preview release | [R01 #26](https://github.com/ozdemirr1/opsdesk/issues/26) | Full scoped backend acceptance and operational evidence; the identity preview is narrower |

The original Month 04 frontend MVP is incomplete. On 25 October, the learner
approved an intensive 26 October–1 November plan: 42 focused hours plus up to
8 contingency hours, replacing the earlier 18-hour proposal. Required deliveries
include scoped reads/title search, real Organization/list/detail integration and
protected routes, persisted comments, a role-aware priority action, the complete
Tailwind/responsive/sidebar/empty-state/toast/modal/accessibility package and
verification/release/learning evidence. Re-estimate Tuesday and Friday; unmet
acceptance gates require an explicit calendar correction, not reduced UI scope
or a false completion claim. F12 is covered only for priority; assignment, full
status workflow and membership administration remain separate backend backlog.
The plan itself is not completion evidence; the local read implementation below
now covers its first backend slice. See the
[detailed plan](https://github.com/ozdemirr1/ai-backend-bootcamp/blob/main/weekly-reports/week-16-plan.md).

## Verification and live recovery

Fresh local baseline on 26 October at `3d0e10b`: backend 506 non-integration
passed/160 deselected; Ruff check and format passed (112 files). Frontend 141
tests/10 files passed with one worker; build/lint passed. The first parallel test
run failed before running tests with ENOSPC; low disk space remains an environment
limitation, not a fixed application bug. These figures describe the pre-change
baseline; the completed read slice has newer backend results below.

The [Ticket read/search contract](api-contract.md#ticket-read-contract--26-october-2026)
and access decision table were prepared and then implemented on 26 October.
Final local results: **583 non-integration tests passed / 181 deselected**,
**178 PostgreSQL data tests passed**, Ruff lint/format passed. The new cases
cover scoped reads, query validation, access changes and count/page consistency.
The three schema tests were not rerun; their last result remains 5 October.
No migration or frontend behavior changed. See the
[F11 evidence](issues/f11.md#week-16-local-implementation--26-october-2026).
These local results do not establish a deployed release. GitHub reports CI and
merge state; the last verified live source is recorded below.

Both [Backend CI](https://github.com/ozdemirr1/opsdesk/actions/runs/40193369253)
and [Frontend CI](https://github.com/ozdemirr1/opsdesk/actions/runs/40193369467)
passed at the Week 15 merge `122c052`. Backend CI does not run PostgreSQL suites.

Railway deployment `e7aa38ac-cb26-46f1-937a-e044241a8405` succeeded on
25 October at 15:19:33 Europe/Istanbul with source
`255f9374a6506e1e50dfec0181f39c0b93fec2f4`. At that checkpoint its file tree
matched `122c052`; subsequent documentation commits do not change the runtime.
The deployment still tracks `feature/week-15-railway-preview`; preserve that
branch until an explicit source-branch change is coordinated.

Independent public liveness/readiness checks returned 200 on 25 October. The
learner confirmed the current live interface; a public browser capture also
confirms the mock table/filter/detail UI. Readiness proves database connectivity,
not all schema privileges or authorization. Today's duplicate-registration,
wrong-password and reload cases were not independently rerun.

Credential rotation was learner-reported on 23 October. Provider audit review,
bounded abuse controls, the stop/export plan and isolated restore/rollback
evidence remain open. Chrome Usage inspection on 26 October showed two services
online, $0.54 current usage ($0.5411 project detail), $4.46 remaining credit and
22 days remaining. The panel showed a $0.00 current bill; no paid upgrade,
configuration change or deployment was made. This balance is a point-in-time
observation, not a cost forecast. Recovery alone does not prove absence of
incident exposure. The conditional Azure migration is no longer needed for the
resolved pause; no paid plan or provider change is implied.

Historical daily evidence is in the
[Week 15 report](https://github.com/ozdemirr1/ai-backend-bootcamp/blob/main/weekly-reports/week-15.md).
