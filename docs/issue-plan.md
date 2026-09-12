# Week 09 Issue Plan

Drafted and reviewed: Saturday, 12 September 2026.

This document preserves four learner-authored issue drafts and their review.
It is a partial planning artifact, not a completed or published GitHub backlog.
No GitHub issue numbers have been assigned here, and no implementation or
executable tests have been completed. GitHub publication remains Furkan's task.

Use the [API baseline](api-contract.md), [domain model](domain-model.md),
[relational model](relational-model.md), and [access-control matrix](access-control.md)
as the reviewed inputs. The Week 09 implementation gate remains open.

## Finalize Ticket Creation Validation Contract

**Title:** Finalize ticket creation validation contract

**Status:** Reviewed design-issue draft; its decisions have not yet been made.

**Goal:** Make ticket creation request validation rules, string bounds, whitespace
normalization, and rejected fields unambiguous before implementing the endpoint.

**Scope:**

- Define exact string length limits and whitespace behavior for title and description.
- Document behavior for omitted, null, and invalid priority values.
- Define accepted fields and rejection of every other field.

**Out of scope:** Endpoint, routing, database-query, and executable-test implementation.

**Acceptance criteria:**

- Only title, description, and optional priority are accepted.
- Reject all other fields, including ticket_id, organization_id,
  requester_membership_id, creator_membership_id, assignee_membership_id, status,
  created_at, and updated_at, even if values match server-derived values.
- Document exact minimum and maximum title/description lengths, the length unit,
  normalization's effect on stored values, and whether length is measured before
  or after normalization.
- Omitted priority defaults to medium. Invalid types, lengths, whitespace-only
  required text, invalid priority, and forbidden fields produce 422 validation_error.
- Provide reviewed valid, boundary, and invalid JSON request examples.

**Expected test cases to specify:**

- Valid creation with omitted priority and with every supported priority value.
- Missing, null, and non-string title/description; exact bounds and just outside them.
- Whitespace-only text containing spaces, tabs, or newlines.
- Null, empty, unknown, and wrong-type priority.
- Server-controlled fields, including matching values, and an unrelated unknown field.

**Dependencies:** Reviewed Week 09 baselines; no outstanding issue dependency
identified. Blocks implementation of Ticket creation validation. The output is a
reviewed contract and examples, not passing application tests.

## Implement Ticket Creation for the Authenticated Member

**Title:** Implement ticket creation for the authenticated member

**Status:** Reviewed development-issue draft; implementation is blocked by prerequisites.

**Goal:** Enable authorized members to create support tickets in their Organization
with correct attribution, integrity, and the defined response.

**Scope:**

- Implement POST /organizations/{organization_id}/tickets and the reviewed validation.
- Check active User, membership, and Organization; derive actor membership references.
- Persist the initial Ticket state within an explicitly owned transaction.
- Return TicketResponse only after a successful commit.

**Out of scope:** Changing validation policy; assignment workflows, comments,
status transitions, email, and background jobs.

**Acceptance criteria:**

- All four roles can create for self when User, membership, and Organization are active.
- Stored organization_id matches the path; requester_membership_id and
  creator_membership_id both match the actor's membership in that Organization.
- A valid creation persists status=open and assignee_membership_id=null.
- Omitted priority becomes medium; a valid supplied priority is preserved.
- Server-controlled fields are rejected with 422 validation_error even when matching
  intended values; invalid request fields also receive 422 validation_error.
- Successful commit returns 201 Created with TicketResponse.
- Missing, invalid, or expired authentication, or an inactive current User, returns
  401 unauthenticated.
- Missing/inactive target membership returns 403 organization_access_denied.
- An active member targeting a suspended Organization receives 403 organization_suspended.
- Rejected creation persists no new Ticket. Persistence failure rolls back, returns
  no success response, and leaves no new Ticket visible from a fresh database session.

**Expected tests:**

- Successful creation by each role, verifying persisted attribution, initial state,
  priority behavior, and response fields as well as HTTP status.
- Separate otherwise-valid requests exercise each authentication, membership,
  Organization, forbidden-field, and validation failure above.
- Simulated persistence failure leaves no new Ticket when independently reloaded.

**Dependencies:** Ticket validation contract; authentication/current-user resolution;
Users, Organizations, OrganizationMemberships, and Tickets schema; guarded PostgreSQL
integration-test infrastructure using opsdesk_test. Exact remaining error precedence
and transaction coordination follow the API baseline's open review items.

## Establish the Backend Application Foundation

**Title:** Establish the backend application foundation

**Status:** Reviewed development-issue draft.

**Goal:** Establish an executable FastAPI application, configuration management,
and local development tooling for subsequent feature work.

**Scope:** Reproducible dependencies; safe settings validation; application creation
and lifecycle; Ruff and pytest configuration; README development workflow.

**Out of scope:** Database connections, migrations, domain tables, database-test
provisioning, business endpoints/routing, authentication, CI/CD, and Docker.

**Acceptance criteria:**

- README documents the supported Python version and one installation, startup,
  linting, formatting-check, and test workflow.
- Runtime and development dependency versions are reproducible.
- Application creation, settings, and tests have separate responsibilities.
- Supported settings, defaults, and genuinely required values are documented.
- Valid configuration permits startup without database or authentication services.
- Invalid configuration prevents startup without exposing sensitive values.
- Local /docs and /openapi.json are served successfully.
- Ruff lint/format checks and meaningful startup/configuration tests pass.

**Expected tests:**

- Valid configuration permits startup and shutdown and expected documentation/OpenAPI responses.
- Invalid supported settings prevent startup; any genuinely required missing setting fails.
- Tests control their configuration without relying on the developer's .env.

**Dependencies:** No implementation-issue dependency; starts after the Week 09 gate.
Choose and document the dependency workflow before implementation. Do not add an
unused required database/JWT setting or a health endpoint merely to make a test pass.
Minimal CI becomes eligible after executable code and meaningful tests exist.

## Establish Guarded PostgreSQL Integration Tests

**Title:** Establish guarded PostgreSQL integration tests

**Status:** Reviewed direction; isolation method and verification details remain open.

**Goal:** Establish isolated PostgreSQL test infrastructure with a restricted target,
reliable session management, and isolation between test scopes.

**Scope:**

- Synchronous SQLAlchemy engine/session-factory setup with separate application
  and integration-test configuration; explicit cleanup and transaction ownership.
- Exact test-database and permitted server-target validation.
- Isolation compatible with application commits and exceptions.
- Database credentials supplied through environment configuration.

**Out of scope:** Business schemas, their migrations/tests, domain repositories,
business transaction workflows, CI/CD, and Docker Compose.

**Acceptance criteria:**

- Integration tests accept only the exact database name opsdesk_test.
- Reject opsdesk_dev and every other name, including another_test.
- Restrict the allowed server target explicitly; a database name alone is insufficient.
- Validate the target before any destructive setup or cleanup.
- Cleanup still runs when the test body raises an exception.
- Exclude passwords and full connection URLs from application logs, error output,
  and surfaced exception traces.
- README documents local PostgreSQL provisioning and guarded test execution.

**Expected tests:**

- Rejected targets raise an error and never reach destructive setup/cleanup functions.
- A controlled verification exercises two successive isolated scopes: a record in a
  test-only probe table from the first is absent in the second.
- Verification is independent of business schemas and test execution order.
- Simulated connection failure exposes neither a synthetic password nor full URL
  in captured application logs or error output.

**Dependencies:** Backend application foundation.

**Sunday follow-up:** Select the concrete isolation method and show its compatibility
with application commits. Add explicit verification for committed probe writes,
cleanup after a test exception, and connection/session release. Do not substitute
two order-dependent tests or an assertion that the entire database is empty.
Business-schema tests arrive with the corresponding schema work. Test-only target
restrictions must not accidentally prohibit the application's legitimate development
database configuration. These are verification targets, not implemented guarantees.

## Preliminary Dependency Map

This map is not a final implementation sequence. Entries without full drafts still
require scope, acceptance criteria, test expectations, priority, and labels.

| Work item | Prerequisites / sequencing notes | Draft state |
| --- | --- | --- |
| Backend application foundation | Week 09 review gate; no implementation prerequisite | Reviewed draft above |
| Ticket creation validation contract | Reviewed domain/API baseline; can be prepared independently of infrastructure | Reviewed draft above |
| Identity validation and authentication contracts | Reviewed identity baseline; resolves email, password, and login-error decisions | Title and purpose only |
| Guarded PostgreSQL integration tests | Backend foundation; includes bounded engine/session setup | Draft with isolation follow-up |
| Initial identity and organization schema | Guarded test infrastructure; schema-affecting identity decisions | Preliminary scope only |
| Ticket schema | Initial identity/organization schema; schema-affecting Ticket validation decisions | Preliminary scope only |
| Authentication and current-user resolution | Users schema and identity/authentication contract | Preliminary scope only |
| Ticket creation implementation | Ticket validation, authentication, required schemas, guarded integration tests | Reviewed draft above |
| Minimal backend CI | Executable package and meaningful tests; then bounded install/Ruff/pytest checks | Needs full draft |

Ticket schema and authentication work can progress independently after their own
prerequisites. Design work need not wait for executable infrastructure. Tests of
business-table constraints belong to schema issues, avoiding a circular dependency
with the earlier test-infrastructure setup.

## Sunday Carry-Over - 13 September

Furkan chose to stop new drafting on Saturday. Preserve the four drafts above;
do not restart them or represent the backlog as complete.

- Resolve the guarded-test isolation choice and verification gaps.
- Draft remaining identity/schema and feature work, including Organization creation
  and visibility, memberships/ownership, Ticket reads/assignment/lifecycle, Comments,
  remaining validation/error/pagination/concurrency decisions, and test coverage.
- Give deferred Attachment migration timing an explicit scope decision; do not
  silently turn metadata endpoints into Month 03 work.
- Prioritize and label bounded issues, review dependencies, and sequence Week 10.
- Include minimal CI at the first meaningful-test stage and the Month 03 deployed
  backend preview carry-over; no Docker build before the scheduled Docker phase.
- Have Furkan publish the reviewed issues on GitHub and record their real links.
- Complete the full Week 09 design review, architecture interview, weekly report,
  and Week 10 handoff. These are not completed by the four drafts alone.

Estimated Sunday active time: 3-4 hours including the carried-over backlog and
weekly review. Keep any unfinished item visible if the available session is shorter.
The existing bounded career/networking routine remains part of the weekly plan.
