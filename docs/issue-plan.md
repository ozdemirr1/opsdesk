# Week 09 Issue Plan

Published backlog: Sunday, 13 September 2026.

Furkan published all 26 reviewed issues from source commit `3ad42fe`. The inventory
below maps local planning identifiers to verified GitHub issue numbers. All 26 were
open at publication; creating an issue does not complete its design or implementation.

GitHub issues are the live source for work status, scope discussion, and completion
evidence. Files in `docs/issues/` preserve the initial published scope. Update the
product requirements, API contracts, and domain documents when accepted behavior
changes; keep this index's links accurate without duplicating daily issue status.

Local IDs such as D01/F01 remain stable document references, not GitHub numbers.
Dependency links in published issue bodies point to actual prerequisite issues.
These Markdown links do not themselves configure GitHub's native blocking relations.

## Published Priorities and Labels

- P0: early prerequisite for the first executable backend slices. This is planned
  sequence, not an incident severity or a promise that every P0 fits Week 10.
- P1: required Month 03 feature, verification, or delivery work following prerequisites.
- Published labels: priority:P0, priority:P1, type:design, type:infrastructure,
  type:schema, type:feature, type:quality, type:delivery. All eight labels were created.
- All work remains week-based; GitHub titles may use the established week prefix
  where appropriate. Do not infer branch creation from this planning document.

## Published Inventory and Dependencies

| Local ID | GitHub issue | Issue title | Priority | Type label | Direct dependencies |
| --- | --- | --- | --- | --- | --- |
| [D01](issues/d01.md) | [#1](https://github.com/ozdemirr1/opsdesk/issues/1) | Finalize ticket creation validation contract | P0 | type:design | Reviewed baseline / gate |
| [D02](issues/d02.md) | [#2](https://github.com/ozdemirr1/opsdesk/issues/2) | Finalize identity validation and authentication contracts | P0 | type:design | Reviewed baseline / gate |
| [D03](issues/d03.md) | [#3](https://github.com/ozdemirr1/opsdesk/issues/3) | Finalize remaining API validation and response contracts | P0 | type:design | Reviewed baseline / gate |
| [D04](issues/d04.md) | [#4](https://github.com/ozdemirr1/opsdesk/issues/4) | Define coordinated transaction and concurrency rules | P0 | type:design | Reviewed baseline / gate |
| [B01](issues/b01.md) | [#5](https://github.com/ozdemirr1/opsdesk/issues/5) | Establish the backend application foundation | P0 | type:infrastructure | Reviewed baseline / gate |
| [B02](issues/b02.md) | [#6](https://github.com/ozdemirr1/opsdesk/issues/6) | Establish guarded PostgreSQL integration tests | P0 | type:infrastructure | [B01](issues/b01.md) |
| [B03](issues/b03.md) | [#7](https://github.com/ozdemirr1/opsdesk/issues/7) | Create the initial identity and organization schema | P0 | type:schema | [B02](issues/b02.md), [D02](issues/d02.md) |
| [B04](issues/b04.md) | [#8](https://github.com/ozdemirr1/opsdesk/issues/8) | Create the ticket schema | P0 | type:schema | [B03](issues/b03.md), [D01](issues/d01.md) |
| [Q01](issues/q01.md) | [#9](https://github.com/ozdemirr1/opsdesk/issues/9) | Add minimal backend continuous integration | P0 | type:quality | [B01](issues/b01.md) |
| [Q02](issues/q02.md) | [#10](https://github.com/ozdemirr1/opsdesk/issues/10) | Implement shared API errors and safe request logging | P0 | type:infrastructure | [B01](issues/b01.md), [D03](issues/d03.md) |
| [F02](issues/f02.md) | [#11](https://github.com/ozdemirr1/opsdesk/issues/11) | Implement user registration | P0 | type:feature | [D02](issues/d02.md), [B03](issues/b03.md), [Q02](issues/q02.md) |
| [F03](issues/f03.md) | [#12](https://github.com/ozdemirr1/opsdesk/issues/12) | Implement login and access-token issuance | P0 | type:feature | [D02](issues/d02.md), [B03](issues/b03.md), [Q02](issues/q02.md) |
| [F04](issues/f04.md) | [#13](https://github.com/ozdemirr1/opsdesk/issues/13) | Implement authenticated current-user resolution | P0 | type:feature | [D02](issues/d02.md), [B03](issues/b03.md), [Q02](issues/q02.md) |
| [F05](issues/f05.md) | [#14](https://github.com/ozdemirr1/opsdesk/issues/14) | Implement organization creation with initial ownership | P1 | type:feature | [F04](issues/f04.md), [B03](issues/b03.md), [D03](issues/d03.md), [D04](issues/d04.md) |
| [F06](issues/f06.md) | [#15](https://github.com/ozdemirr1/opsdesk/issues/15) | Implement organization listing and detail visibility | P1 | type:feature | [F04](issues/f04.md), [B03](issues/b03.md), [D03](issues/d03.md) |
| [F07](issues/f07.md) | [#16](https://github.com/ozdemirr1/opsdesk/issues/16) | Implement staff-only membership directory | P1 | type:feature | [F04](issues/f04.md), [B03](issues/b03.md), [D03](issues/d03.md) |
| [F08](issues/f08.md) | [#17](https://github.com/ozdemirr1/opsdesk/issues/17) | Implement member addition and membership reactivation | P1 | type:feature | [F04](issues/f04.md), [B03](issues/b03.md), [D02](issues/d02.md), [D03](issues/d03.md), [D04](issues/d04.md) |
| [F01](issues/f01.md) | [#18](https://github.com/ozdemirr1/opsdesk/issues/18) | Implement ticket creation for the authenticated member | P1 | type:feature | [D01](issues/d01.md), [D03](issues/d03.md), [D04](issues/d04.md), [B04](issues/b04.md), [F04](issues/f04.md), [Q02](issues/q02.md) |
| [F11](issues/f11.md) | [#19](https://github.com/ozdemirr1/opsdesk/issues/19) | Implement scoped ticket listing and detail retrieval | P1 | type:feature | [F04](issues/f04.md), [B04](issues/b04.md), [D03](issues/d03.md) |
| [F12](issues/f12.md) | [#20](https://github.com/ozdemirr1/opsdesk/issues/20) | Implement ticket priority and assignment operations | P1 | type:feature | [F04](issues/f04.md), [B04](issues/b04.md), [D03](issues/d03.md), [D04](issues/d04.md) |
| [F13](issues/f13.md) | [#21](https://github.com/ozdemirr1/opsdesk/issues/21) | Implement ticket lifecycle transitions and reopening cleanup | P1 | type:feature | [F04](issues/f04.md), [B04](issues/b04.md), [D03](issues/d03.md), [D04](issues/d04.md) |
| [F09](issues/f09.md) | [#22](https://github.com/ozdemirr1/opsdesk/issues/22) | Implement membership role changes and deactivation | P1 | type:feature | [F04](issues/f04.md), [B04](issues/b04.md), [D03](issues/d03.md), [D04](issues/d04.md) |
| [F10](issues/f10.md) | [#23](https://github.com/ozdemirr1/opsdesk/issues/23) | Implement atomic organization ownership transfer | P1 | type:feature | [F04](issues/f04.md), [B03](issues/b03.md), [D03](issues/d03.md), [D04](issues/d04.md) |
| [F14](issues/f14.md) | [#24](https://github.com/ozdemirr1/opsdesk/issues/24) | Implement ticket comments with tenant-safe persistence | P1 | type:feature | [F04](issues/f04.md), [B04](issues/b04.md), [D03](issues/d03.md), [D04](issues/d04.md) |
| [Q03](issues/q03.md) | [#25](https://github.com/ozdemirr1/opsdesk/issues/25) | Run guarded PostgreSQL integration tests in CI | P1 | type:quality | [Q01](issues/q01.md), [B02](issues/b02.md), [B04](issues/b04.md) |
| [R01](issues/r01.md) | [#26](https://github.com/ozdemirr1/opsdesk/issues/26) | Publish the first OpsDesk backend preview | P1 | type:delivery | [Q03](issues/q03.md), [Q02](issues/q02.md), [F01](issues/f01.md), [F02](issues/f02.md), [F03](issues/f03.md), [F04](issues/f04.md), [F05](issues/f05.md), [F06](issues/f06.md), [F07](issues/f07.md), [F08](issues/f08.md), [F09](issues/f09.md), [F10](issues/f10.md), [F11](issues/f11.md), [F12](issues/f12.md), [F13](issues/f13.md), [F14](issues/f14.md) |

Prerequisites are acceptance gates, not just a suggested reading order. A completed
registration endpoint is not required to test login or current-user resolution;
controlled records and library-generated test tokens can supply fixtures.
Business-table tests arrive with schema work, not before those tables exist.

## Endpoint Coverage

Every endpoint in the current 22-endpoint baseline is assigned once below. No
Attachment metadata, deletion, global account-deactivation, or suspension endpoint
is introduced by this backlog. Infrastructure has its own issues rather than being
counted as extra product endpoints.

| Method and path | Implementation issue |
| --- | --- |
| `POST /users` | [F02](issues/f02.md) |
| `POST /auth/login` | [F03](issues/f03.md) |
| `GET /users/me` | [F04](issues/f04.md) |
| `POST /organizations` | [F05](issues/f05.md) |
| `GET /organizations` | [F06](issues/f06.md) |
| `GET /organizations/{organization_id}` | [F06](issues/f06.md) |
| `POST /organizations/{organization_id}/tickets` | [F01](issues/f01.md) |
| `GET /organizations/{organization_id}/tickets` | [F11](issues/f11.md) |
| `GET /organizations/{organization_id}/tickets/{ticket_id}` | [F11](issues/f11.md) |
| `PUT /organizations/{organization_id}/tickets/{ticket_id}/priority` | [F12](issues/f12.md) |
| `PUT /organizations/{organization_id}/tickets/{ticket_id}/status` | [F13](issues/f13.md) |
| `PUT /organizations/{organization_id}/tickets/{ticket_id}/assignment` | [F12](issues/f12.md) |
| `DELETE /organizations/{organization_id}/tickets/{ticket_id}/assignment` | [F12](issues/f12.md) |
| `POST /organizations/{organization_id}/tickets/{ticket_id}/comments` | [F14](issues/f14.md) |
| `GET /organizations/{organization_id}/tickets/{ticket_id}/comments` | [F14](issues/f14.md) |
| `GET /organizations/{organization_id}/memberships` | [F07](issues/f07.md) |
| `POST /organizations/{organization_id}/memberships` | [F08](issues/f08.md) |
| `POST /organizations/{organization_id}/memberships/{membership_id}/reactivation` | [F08](issues/f08.md) |
| `PUT /organizations/{organization_id}/memberships/{membership_id}/role` | [F09](issues/f09.md) |
| `DELETE /organizations/{organization_id}/memberships/{membership_id}` | [F09](issues/f09.md) |
| `DELETE /organizations/{organization_id}/memberships/me` | [F09](issues/f09.md) |
| `POST /organizations/{organization_id}/ownership-transfer` | [F10](issues/f10.md) |

## Selected Test Isolation Policy

Sunday's reviewed direction uses real application commits plus explicit DELETE
cleanup transactions on an allowlist. Exact database/server validation precedes
destructive work; preserve migration history. One suite owns the test database at a
time. An individual concurrency test may coordinate multiple independent sessions,
then finish all work before cleanup. Roll back unfinished transactions and close
sessions before cleanup; do not hide either the original failure or cleanup failure.
Validated cleanup also runs at the start to handle leftovers from interrupted runs.

B02 specifies probe-table verification without business schemas. B03/B04/F14 extend
the cleanup allowlist with their own tables. Migration tests change schema separately
from data tests and restore it before ordinary tests proceed. This remains a planned
implementation, not a tested guarantee.

## Open Decisions and Readiness

- D01 outcomes were reviewed on 15 September: see the
  [Ticket creation validation contract](ticket-creation-validation.md) for chosen
  values, normalization, and examples. Implementation and GitHub closure are separate.
- D02 outcomes were reviewed on 15 September: see the
  [identity/authentication contract](identity-authentication-contract.md) for email,
  password, duplicate registration, login, and JWT decisions. Implementations still
  require their own code and test evidence; issue closure remains Furkan's task.
- D03 Organization name rules were reviewed on 17 September; see the
  [name contract](api-contract.md#organization-name-contract). This supplies the
  name bounds needed by B03, not completion of D03.
- D03 collects remaining membership/Comment validation, list and response
  shapes, error precedence, repeated-operation outcomes, timestamps, safe logging, and
  Attachment migration timing. Proposed filters are not automatically accepted features.
- D04 has an accepted [cooperating lock protocol](concurrency-contract.md), recorded
  on 22 September: Organization coordination, ordered locks, fresh validation,
  2-second per-lock waits, and 503 concurrency_busy without automatic retries.
  Implementation/concurrency tests remain future work; no GitHub closure is claimed.
- No full Week 09 completion claim is made merely because every endpoint has a draft.
  Backlog publication and architecture review are complete. The bootcamp repository
  records the Week 09 report and Week 10 handoff; final Git closure remains pending.

## Week 10 Handoff Sequence

Capacity target: approximately 15-20 active hours, to be adjusted as work proceeds. This
is a dependency-respecting plan, not a commitment to implement all 26 issues.

1. Resolve D01/D02 and the early shared-error/settings portions of D03; identify any
   remaining prerequisite decisions before their dependent work starts.
2. B01: establish executable foundation and meaningful tests. Then Q01 can add fast CI.
3. B02: establish guarded PostgreSQL sessions and verify real-commit cleanup.
4. B03: apply identity/Organization schema after schema-affecting D02 decisions
   and the reviewed D03 Organization name bounds.
5. Complete required D03 outcomes and Q02 shared error/logging behavior before feature
   endpoints depend on them. Continue D04 design before coordinated mutation work.
6. First authentication slice: F02 registration, then F03 login and F04 current-user
   resolution as capacity permits. Login and resolution need not block each other.
7. B04/F01 and remaining Organization/membership/Ticket/Comment slices follow their
   prerequisites in later available Month 03 capacity; do not force them into Week 10.

If design work consumes the available time, record the carry-over explicitly. Minimal
CI starts with real fast tests; guarded database CI is Q03 after the relevant schema
and test infrastructure. R01 preserves the Month 03 deployed preview carry-over and
requires release evidence; Docker/Compose remains outside this phase.

## Publication and Weekly Closure

- Completed: Furkan published the reviewed backlog and eight labels; all 26 issue
  titles, identifiers, labels, and dependency links were verified against GitHub.
- Completed: grouped Sunday architecture review; precision corrections, Week 09
  report, and capacity-bounded Week 10 handoff are recorded in the bootcamp repository.
- No completed career action was evidenced; carry the bounded preparation task
  explicitly into Week 10 rather than treating it as done.
- Perform documentation checks and Furkan's staged review/commit/push in both repos.
  A clean draft is not equivalent to an implemented feature, passing API tests, or CI.
