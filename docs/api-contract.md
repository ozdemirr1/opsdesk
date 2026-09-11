# API Contract Baseline

Reviewed: Week 09 Friday, 11 September 2026.

This document consolidates the endpoint drafts and mentoring corrections. It is a
design baseline, not an implemented API or a complete OpenAPI specification. Read
it with the [access-control matrix](access-control.md),
[Ticket lifecycle](ticket-lifecycle.md), and [requirements](requirements.md).
Unresolved details are listed explicitly at the end. The Week 09 issue backlog
and implementation gate remain pending.

## Shared Request and Response Rules

- Protected operations authenticate the token and load the current active User.
  A previously issued token does not override current account or membership state.
- Organization-scoped operations require an active membership in the path
  Organization. Ticket, Comment, and membership operations also require an active
  Organization. The limited organization list/detail exception is described below.
- Identified resources and target memberships must belong to the path Organization.
  Ticket visibility and operation permission are separate checks.
- Accept only explicitly defined request fields. Derive actor identities and parent
  references on the server; never accept role, ownership, status, or assignment
  through an unrelated request schema. Invalid supplied values are not defaults.
- Successful writes return only after their transaction commits. Rejected operations
  leave durable business data unchanged. No-op responses make no business writes.
- Responses use explicit public field projections rather than serialized ORM objects.
  Passwords, password hashes, secrets, internal SQL, and stack traces are excluded.
  Login is the deliberate access-token response; tokens must never enter error output.
- Tables below describe JSON bodies unless a query or no body is specified.
  All list responses use the common pagination envelope.

## Identity and Organizations

| Purpose | Method and path | Input | Authorization and behavior | Success |
| --- | --- | --- | --- | --- |
| Register | `POST /users` | email, password | Public; server controls identity and active state | 201 UserProfile |
| Log in | `POST /auth/login` | email, password | Public entry point; valid credentials for an active User required | 200 access_token and token_type="bearer" |
| Read current identity | `GET /users/me` | None | Active authenticated User | 200 UserProfile |
| Create organization | `POST /organizations` | name | Any active authenticated User; create active Organization and actor's active owner membership atomically | 201 Organization and initial membership |
| List my organizations | `GET /organizations` | Optional query: is_active; pagination | Active User; only Organizations with an active actor membership, including suspended Organizations | 200 paginated items containing Organization and own membership |
| Read organization | `GET /organizations/{organization_id}` | None | Active User and active target membership; Organization may be suspended | 200 Organization |

UserProfile fields: user_id, email, is_active. Organization fields:
organization_id, name, is_active. The own-membership projection contains
membership_id, organization_id, role, is_active; it is not a directory of other members.

Organization creation is a global capability: there is no pre-existing target
membership to authorize. The initial owner comes from the authenticated actor, never
from the body. Failure to create that membership rolls back Organization creation.

Suspended Organizations remain discoverable through these basic list/detail views
for active members. This exception does not permit reading Tickets, Comments, the
membership directory, or performing Organization-scoped mutations. Inactive
membership removes even this visibility. The final nested organization-list and
creation response layouts still need example-based review.

Refresh tokens are outside Month 03. Password limits, email canonicalization,
duplicate registration, and credential-failure details require the remaining review.

## Tickets

| Purpose | Method and path | Input | Authorization and behavior | Success |
| --- | --- | --- | --- | --- |
| Create for self | `POST /organizations/{organization_id}/tickets` | title, description; optional priority | All four roles; open and unassigned; requester and creator derived from actor | 201 TicketResponse |
| List | `GET /organizations/{organization_id}/tickets` | Optional query: status, priority, assignee_membership_id; pagination | Customers: requested by self; staff: all in Organization | 200 paginated TicketResponse items |
| Read | `GET /organizations/{organization_id}/tickets/{ticket_id}` | None | Same visibility scope; Ticket must belong to path Organization | 200 TicketResponse |
| Set priority | `PUT /organizations/{organization_id}/tickets/{ticket_id}/priority` | priority | Staff, any visible same-Organization Ticket; only open/in_progress | 200 TicketResponse |
| Set status | `PUT /organizations/{organization_id}/tickets/{ticket_id}/status` | status | Exact transition permission, state preconditions, and same-status policy | 200 TicketResponse |
| Assign or reassign | `PUT /organizations/{organization_id}/tickets/{ticket_id}/assignment` | Non-null assignee_membership_id | Assignment matrix; open/in_progress; currently eligible target | 200 TicketResponse |
| Remove assignment | `DELETE /organizations/{organization_id}/tickets/{ticket_id}/assignment` | None | Assignment matrix; only open | 200 TicketResponse with null assignee |

Omitted creation priority becomes medium. Null or unknown priority fails validation.
Creation rejects supplied status, assignee, requester, creator, and organization
fields, including values that happen to match the server's intended values.

Eligible assignees have an active global User and active same-Organization membership
with role agent/admin/owner. Agents may distribute unassigned work, but only reassign
their own existing assignments. Admins/owners may reassign any in-scope Ticket.

The proposed unassigned-queue filter is `assignment=assigned|unassigned`; omission
means both. Combining unassigned with assignee_membership_id would be a 422 error.
Finalize this query extension before implementation: a numeric assignee ID alone
cannot represent NULL, and filters must never widen the caller's visibility scope.

### TicketResponse Example

This learner-authored example represents a successfully committed creation. It
contains all selected TicketResponse fields; it is not a creation request body.
Timestamps use an explicit UTC offset, shown here as Z.

```json
{
  "ticket_id": 105,
  "organization_id": 42,
  "title": "Cannot access the reporting dashboard",
  "description": "Every time I click on the weekly report, the page freezes.",
  "priority": "medium",
  "status": "open",
  "requester_membership_id": 88,
  "creator_membership_id": 88,
  "assignee_membership_id": null,
  "created_at": "2026-09-11T14:45:00Z",
  "updated_at": "2026-09-11T14:45:00Z"
}
```

### Repeated Requests and No-ops

A no-op is an authorized request that leaves business state unchanged. It does not
refresh updated_at or run transition side effects. Authenticate, validate scope and
visibility, validate input, and establish the applicable operation permission before
returning a successful no-op. Framework validation ordering must not bypass these guards.

| Situation | Response | Persistent effect |
| --- | --- | --- |
| Authorized staff repeats current priority on an open Ticket | 200 | None; priority status limits still apply |
| Actor repeats current status with the explicit same-status permission | 200 | None; no reopening cleanup |
| Agent repeats reassignment after transferring work to another member | 403 permission_denied | None; assigned-to-self condition no longer holds |
| Admin removes assignment from an already unassigned open Ticket | 200 | None |

The [same-status permission table](ticket-lifecycle.md#same-status-requests) is
distinct from visibility and real transitions. Seeing a resolved Ticket does not
authorize a customer to PUT resolved, even when that value is already stored.

HTTP idempotency concerns the intended effect of repeated requests, not identical
responses. It does not mandate returning 200 after the caller loses permission.
Same-assignee PUT and other repeated membership operations still need explicit
case-by-case contracts; do not generalize this table into a universal shortcut.

## Comments and Memberships

| Purpose | Method and path | Input | Authorization and behavior | Success |
| --- | --- | --- | --- | --- |
| Add comment | `POST /organizations/{organization_id}/tickets/{ticket_id}/comments` | content | Visible Ticket plus posting permission; open/in_progress/resolved; actor-derived author | 201 CommentResponse |
| List comments | `GET /organizations/{organization_id}/tickets/{ticket_id}/comments` | Pagination | Parent Ticket visibility, including closed | 200 paginated CommentResponse items |
| List memberships | `GET /organizations/{organization_id}/memberships` | Optional query: role, is_active; pagination | agent/admin/owner only | 200 paginated MembershipResponse items |
| Add existing User | `POST /organizations/{organization_id}/memberships` | Exact email, role: customer/agent | Admin/owner; active target global User; no existing membership in any state | 201 active MembershipResponse |
| Reactivate membership | `POST /organizations/{organization_id}/memberships/{membership_id}/reactivation` | role: customer/agent | Admin/owner; different inactive non-owner membership; active target User | 200 active MembershipResponse |
| Change another member's role | `PUT /organizations/{organization_id}/memberships/{membership_id}/role` | role: customer/agent/admin | Admin/owner; different active non-owner target; customer target requires active-work handover | 200 MembershipResponse |
| Deactivate another membership | `DELETE /organizations/{organization_id}/memberships/{membership_id}` | None | Admin/owner; different active non-owner target; active-work handover | 200 inactive MembershipResponse |
| Leave organization | `DELETE /organizations/{organization_id}/memberships/me` | None | Active non-owner member; active-work handover | 200 inactive own MembershipResponse |
| Transfer ownership | `POST /organizations/{organization_id}/ownership-transfer` | target_membership_id | Current owner; different active User with active same-Organization admin membership; atomic exchange of roles | 200 both updated memberships |

CommentResponse fields: comment_id, author_membership_id, content, created_at.
MembershipResponse fields: membership_id, organization_id, role, is_active.
The directory and mutation responses do not expose global email or account settings.
Named wrappers for the ownership-transfer response remain to be finalized.

The directory's membership is_active filter alone does not establish assignability:
the global User and role must also be eligible. A proposed `assignable=true` filter
would compute these conditions without exposing global account details. Its full
query semantics remain a follow-up. The assignment operation always checks current
eligibility again. Human-readable directory labels are a separate future design.

Add/reactivate accepts customer/agent only, preserving the reviewed membership
matrix. Granting admin requires the separate authorized role update. Neither ordinary
role update nor reactivation may rewrite the owner or change the actor's own role.
Admin-to-agent preserves eligibility; active work alone does not block that change.

Membership DELETE is logical deactivation, retaining the row and historical references.
After leaving, the caller no longer passes active membership authorization on a retry.
Likewise, a former owner cannot repeat ownership transfer using their old authority.
Resolve the static `/memberships/me` route distinctly from the numeric member route.

### Exact-email Addition and Disclosure Limits

Addition is direct membership creation for an existing active User; it is not an
email invitation, consent workflow, or account creation. Match using the same
canonical email policy as registration/login; no partial search or user directory.

Missing and inactive global Users share `400 user_not_addable`, with a safe message
such as "The specified user cannot be added." An existing membership, including an
inactive row, yields `409 membership_exists`; use the explicit reactivation workflow.
Define precedence for overlapping target conditions during the remaining error review.

These responses do not remove account-enumeration risk: successful addition still
reveals that an account is addable. Anyone allowed to create an Organization can
become its owner, so staff-only access is not proof against global account probing.
Record this product tradeoff without claiming that generic errors solve it entirely.

## Error Contract

| Failure | HTTP status | Public code |
| --- | --- | --- |
| Missing, invalid, or expired bearer token; missing/inactive current User | 401 | unauthenticated |
| No active membership in requested Organization, including nonexistent Organization | 403 | organization_access_denied |
| Ticket missing, outside path Organization, or outside caller visibility | 404 | ticket_not_found |
| Visible resource, forbidden operation | 403 | permission_denied |
| Active member requests blocked child access/mutation in suspended Organization | 403 | organization_suspended |
| Invalid request fields, types, enums, or pagination values | 422 | validation_error |
| Permitted operation blocked by current business state | 409 | state_conflict |
| Membership already exists, active or inactive | 409 | membership_exists |
| Email does not identify an addable active User | 400 | user_not_addable |

Protected bearer 401 responses include `WWW-Authenticate: Bearer`. Resolve membership
before exposing Organization suspension. Missing/foreign/invisible Tickets share a
public response; this concealment supplements actual scoped authorization checks.
Role denial and state conflict are distinct; finalize precedence for requests that
violate both, including unlisted transitions, before writing error assertions.

The proposed transport extensions are `400 invalid_json` for malformed JSON and
`415 unsupported_media_type` for unsupported Content-Type. These require explicit
framework handling and acceptance examples; they are not assumed framework defaults.

### Validation Error Example

Expected HTTP status: 422. This learner-authored body uses safe field names and
messages, without echoing rejected raw values or framework exception internals.

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": [
      {
        "field": "priority",
        "message": "Value must be one of: 'low', 'medium', 'high', 'urgent'."
      }
    ]
  }
}
```

Use a consistent error envelope. Decide whether non-field failures use an empty
details array, and define nested/query field paths, before completing response schemas.
Do not include raw request bodies, passwords, tokens, hashes, or database details.

## Pagination and Filtering

- Use integer limit and offset. Default limit: 20; valid range: 1..100.
  Default offset: 0; minimum: 0. Reject invalid values with 422; do not silently clamp.
- Ticket ordering is created_at DESC, ticket_id DESC. The ID breaks timestamp ties;
  it does not prove commit chronology. Other collection orderings remain open.
- Apply caller visibility and client filters before ordering and pagination.
- total_count uses exactly the same visibility and filters, without limit/offset.
  Staff may legitimately count all in-scope Organization Tickets when unfiltered.
- Every collection response uses items, total_count, limit, offset. Empty results
  are 200 with an empty items array, not a bare array or 404.

```json
{
  "items": [],
  "total_count": 0,
  "limit": 20,
  "offset": 0
}
```

An offset beyond 12 matching records returns empty items but total_count=12.
Deterministic ordering does not provide a snapshot across requests: concurrent inserts
or filter-changing updates may shift offsets and cause skipped or repeated records.
The page-size cap bounds returned rows, not all database work or large-offset cost.

The consistency policy between count and items is still open. Separate SELECTs under
PostgreSQL Read Committed can see different snapshots even inside one transaction;
do not promise a single shared snapshot until the repository strategy is selected.

## Deferred Month 03 Operations

| Operation | Scope and rationale |
| --- | --- |
| Edit Ticket title/description | No endpoint; original request remains immutable through product operations. Clarifying comments are allowed only before closed. |
| Delete Ticket | No endpoint; closed ends work but does not erase data. FKs restrict referenced parents, not every possible Ticket deletion. Retention/erasure needs separate design. |
| Rename Organization | Deferred administrative convenience. The display name is distinct from stable Organization identity. |
| Suspend/reactivate Organization through a user endpoint | Deferred actor/workflow design. Inactive state remains relevant to access checks and future test fixtures. No billing workflow is implied. |
| Globally deactivate own User | No endpoint this month. Existing cross-Organization ownership/assignment preconditions remain domain rules for future implementation. |
| Create/read/delete Attachment metadata | No metadata API this month. Domain/relational design remains; file upload/download/storage is also excluded. Metadata can have independent value, but is not required for this release's core workflow. |

Comment edit/delete, internal notes, on-behalf-of Ticket creation, refresh tokens,
email delivery, frontend, background jobs, Docker, and AI retain their existing exclusions.

## Remaining Review and Test Handoff

- Set email canonicalization, password policy, precise string bounds, and request
  validation examples. Review login failures, duplicate registration, missing target
  memberships, unexpected server errors, and overlapping-failure precedence.
- Finalize the proposed queue/directory filters, non-Ticket collection ordering,
  count/items consistency, remaining nested responses, and error details conventions.
- Define same-assignee/same-role updates and repeated reactivation/deactivation
  cases without weakening current authorization.
- Specify cooperating transactions, lock order, and conflict/retry behavior for
  claims, ownership, role changes, deactivation, and reopening. Atomicity alone
  does not resolve races or stale authorization checks.
- Decide when the deferred Attachment table becomes an executable migration.
- Turn these bounded decisions and the 22 endpoints into prioritized issues with
  dependencies and acceptance criteria; this document is not a completed backlog.

Future tests must verify response projections, forbidden/system fields, stale-token
account checks, tenant and requester scoping, no-op authorization and unchanged
timestamps, suspended-Organization exceptions, reactivation privilege boundaries,
rollback, filtering/count consistency, paging bounds, and safe error output.
No application tests or schema changes were executed for this documentation baseline.

## References

- [HTTP semantics: idempotency](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)
- [HTTP semantics: authentication challenges](https://www.rfc-editor.org/rfc/rfc9110.html#section-11.6.1)
- [OWASP authentication and error messages](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#authentication-and-error-messages)
- [PostgreSQL LIMIT and OFFSET](https://www.postgresql.org/docs/18/queries-limit.html)
- [PostgreSQL transaction isolation](https://www.postgresql.org/docs/18/transaction-iso.html)

These references explain protocol and database behavior. OpsDesk's roles, no-op
permissions, response shapes, and release boundaries remain product decisions.
