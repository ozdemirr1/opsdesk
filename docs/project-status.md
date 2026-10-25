# Project status — 25 October 2026

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
| Ticket list/detail | [F11 #19](https://github.com/ozdemirr1/opsdesk/issues/19) | Week 16: scoped queries, service/routes, PostgreSQL authorization tests, then runtime guards and UI |
| Membership directory/add/reactivation | #16, #17 | Needed before meaningful membership administration UI; estimate at Month 04 handoff |
| Priority/assignment and status workflow | #20, #21 | Current-state role checks and cooperating locks; not inert UI buttons |
| Role/deactivation and ownership transfer | #22, #23 | Reviewed invariants and overlapping-operation tests |
| Comments | [F14 #24](https://github.com/ozdemirr1/opsdesk/issues/24) | Comment schema, read/write authorization, service/API tests before form integration |
| PostgreSQL CI | [Q03 #25](https://github.com/ozdemirr1/opsdesk/issues/25) | Dedicated isolated CI database; local passing results do not close this |
| Full backend preview release | [R01 #26](https://github.com/ozdemirr1/opsdesk/issues/26) | Full scoped backend acceptance and operational evidence; the identity preview is narrower |

The original Month 04 frontend MVP is incomplete. Week 16 reserves 12 hours for
real reads/integration, 3 for a bounded UI slice and 3 for verification/handoff.
Re-estimate after Tuesday; if integration expands, explicitly reduce styling scope.
Size unresolved comments/role/workflow and operations at the 1 November handoff;
do not automatically claim them as part of the delivered MVP. See the
[detailed plan](https://github.com/ozdemirr1/ai-backend-bootcamp/blob/main/weekly-reports/week-16-plan.md).

## Verification and live recovery

Last local groups: frontend 141 tests/10 files + build/lint on 24 October;
backend 506 non-integration passed/160 deselected on 19 October;
PostgreSQL 157 data tests and 3 schema tests in separate runs on 5 October.
No fresh full regression is claimed for this documentation update.

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
bounded abuse controls, current trial usage/stop-export plan and isolated
restore/rollback evidence remain open. Recovery alone does not prove absence of
incident exposure. The conditional Azure migration is no longer needed for the
resolved pause; no paid plan or provider change is implied.

Historical daily evidence is in the
[Week 15 report](https://github.com/ozdemirr1/ai-backend-bootcamp/blob/main/weekly-reports/week-15.md).
