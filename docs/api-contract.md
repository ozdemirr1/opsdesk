# API Contract Baseline

Reviewed: Week 09 Friday, 11 September 2026.

This document consolidates the endpoint drafts and mentoring corrections. It is a
design baseline, not an implemented API or a complete OpenAPI specification. Read
it with the [access-control matrix](access-control.md),
[Ticket lifecycle](ticket-lifecycle.md), and [requirements](requirements.md).
Unresolved details are listed explicitly at the end. The Week 09 backlog is
published; dependent implementation still requires its specific design decisions.
Ticket creation validation was reviewed on 15 September; see the linked contract.

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
membership removes even this visibility. Organization creation and list operations
use the reviewed nested projections below; they never expose another User's global
account fields.

The [identity/authentication contract](identity-authentication-contract.md), reviewed
15 September, defines ASCII lowercase canonical email, duplicate registration
(409 email_already_exists), NFC-normalized passwords of 15..128 code points, and
30-minute HS256 tokens with required sub/iat/exp/iss/aud claims. Otherwise valid login
with unknown email, wrong password, or inactive account uses the same public
401 unauthenticated response. Protected requests reload the current active User.
Refresh tokens remain outside Month 03.

### Organization Name Contract

Reviewed with Furkan on 17 September 2026. This resolves the Organization-name
portion of D03 for the initial schema; it does not complete D03 or implement an endpoint.

- `name` is a required string. Missing, null, and non-string values are invalid.
- Reject U+0000, LF (`\n`), CR (`\r`), and TAB (`\t`) before trimming,
  including when they appear at either edge.
- Trim leading/trailing whitespace using Python `str.strip()`. Preserve internal
  spaces, case, Turkish characters, and other Unicode text. Apply no additional
  Unicode normalization or case conversion.
- Measure length after trimming in Unicode code points: minimum 1, maximum 255.
  Whitespace-only values become empty and are invalid.
- Invalid name input returns `422 validation_error`. A valid name alone does not
  guarantee creation: authentication and the atomic Organization/owner write remain required.
- Names are not unique. Distinct Organizations may have identical names; their
  `organization_id` values identify them. No rename endpoint is added by this decision.

| Input | Validation result / normalized value |
| --- | --- |
| `"  Özdemir Yazılım  "` | Accept as `"Özdemir Yazılım"` |
| `"Özdemir  Yazılım"` | Accept; preserve both internal spaces |
| `"   "` or `""` | Reject; empty after trimming |
| `"\tAcme"`, `"Acme\n"`, `"Acme\rTeam"` | Reject before trimming |
| `"Acme\u0000Team"` | Reject NUL |
| `null`, `123`, or omitted name | Reject |
| 255 `A` characters, optionally surrounded by spaces | Accept after trimming |
| 256 `A` characters | Reject |
| Unicode whitespace U+00A0 alone | Reject; empty after Python trimming |

Persist `name` as `text NOT NULL` with `char_length(name) BETWEEN 1 AND 255`.
Input normalization remains an application responsibility; that length CHECK alone
neither trims text nor rejects every whitespace-only value. As with Ticket fields,
any additional database whitespace guard requires shared Unicode edge-case review;
PostgreSQL POSIX whitespace classes must not be assumed identical to Python's.
The initial identity migration and PostgreSQL constraint tests now verify these
storage bounds; the Organization endpoint and input normalizer remain unimplemented.

### Organization Response Structures

Reviewed with Furkan on 24 September 2026. `POST /organizations` accepts only the
reviewed `name` field. The authenticated current User is derived after token
verification and a current persisted-User lookup. The service creates an active
Organization and that User's active owner membership; `user_id`, `role`, and
`is_active` are not client-selected fields.

A successful creation returns a named wrapper rather than flattening two records:

```json
{
  "organization": {
    "organization_id": 42,
    "name": "Özdemir Yazılım",
    "is_active": true
  },
  "own_membership": {
    "membership_id": 81,
    "organization_id": 42,
    "role": "owner",
    "is_active": true
  }
}
```

Each `GET /organizations` item uses the same `organization` and `own_membership`
shape. The surrounding collection uses the common `items`, `total_count`, `limit`,
and `offset` envelope. `GET /organizations/{organization_id}` continues to return
only the Organization projection because its authorization check does not turn the
response into a membership-directory operation.

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

The [Ticket creation validation contract](ticket-creation-validation.md) defines
strict field types, title length 1..255, description length 1..10000, Python-style
edge trimming, code-point length measurement, forbidden text characters, and examples.
Priority accepts only exact low/medium/high/urgent values; omission alone selects medium.
Only title, description, and optional priority are accepted. Reject all other fields,
including matching server-controlled values. Validation acceptance alone is not a
successful creation; authorization and a successful commit are still required.

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

`POST /organizations/{organization_id}/ownership-transfer` returns the two
post-commit membership projections in a named wrapper:

```json
{
  "previous_owner_membership": {
    "membership_id": 81,
    "organization_id": 42,
    "role": "admin",
    "is_active": true
  },
  "new_owner_membership": {
    "membership_id": 96,
    "organization_id": 42,
    "role": "owner",
    "is_active": true
  }
}
```

The names describe each membership's committed state. The response contains no
global User email or account settings.

### Comment and Membership Input Fields

Reviewed with Furkan on 24 September 2026:

- Comment creation accepts exactly one required string field, `content`. Normalize
  CRLF and lone CR to LF, then reject NUL and all remaining C0 control characters
  other than LF and TAB. Trim leading and trailing whitespace with Python
  `str.strip()`. Preserve
  internal LF, TAB, spaces, case, and Unicode text. The normalized content must
  contain 1..10000 Unicode code points. Missing, null, wrong-type, empty-after-trim,
  over-limit, forbidden-control, and extra fields produce `422 validation_error`.
- Member addition accepts exactly `email` and `role`. Email uses the shared identity
  canonicalization contract. Role is an exact `customer|agent` value; it is not a
  free-form string. Reactivation accepts exactly `role` with the same two values.
- Role update accepts exactly `role` with the exact
  `customer|agent|admin` vocabulary. Ownership is never granted through this body.
- Assignment accepts exactly `assignee_membership_id`; ownership transfer accepts
  exactly `target_membership_id`. Body and path membership identifiers are strict
  JSON/Python integers in the PostgreSQL signed-bigint range 1..9223372036854775807;
  booleans, strings, floats, null, zero, negatives, arrays, objects, out-of-range
  integers, and extra body fields are invalid. Resource lookups still enforce tenant
  scope.
- Server-derived actor, author, User, Organization, role/default state, timestamps,
  and parent relationships are rejected if supplied through a client body.

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
| Otherwise valid login with unknown email, wrong password, or inactive account | 401 | unauthenticated |
| No active membership in requested Organization, including nonexistent Organization | 403 | organization_access_denied |
| Ticket missing, outside path Organization, or outside caller visibility | 404 | ticket_not_found |
| Visible resource, forbidden operation | 403 | permission_denied |
| Active member requests blocked child access/mutation in suspended Organization | 403 | organization_suspended |
| Invalid request fields, types, enums, or pagination values | 422 | validation_error |
| Permitted operation blocked by current business state | 409 | state_conflict |
| Membership already exists, active or inactive | 409 | membership_exists |
| Email does not identify an addable active User | 400 | user_not_addable |
| Registration uses an already registered canonical email | 409 | email_already_exists |

Protected bearer 401 responses include `WWW-Authenticate: Bearer`. Resolve membership
before exposing Organization suspension. Missing/foreign/invisible Tickets share a
public response; this concealment supplements actual scoped authorization checks.
Role denial and state conflict are distinct; finalize precedence for requests that
violate both, including unlisted transitions, before writing error assertions.

The [shared error/logging contract](error-logging-contract.md), reviewed on
18 September, accepts `400 invalid_json` and `415 unsupported_media_type`, defines
safe 500/404/405 mappings, and fixes correlation/logging rules. These require
explicit implementation and tests; they are not assumed framework defaults.

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
        "field": "body.priority",
        "message": "Value must be one of: 'low', 'medium', 'high', 'urgent'."
      }
    ]
  }
}
```

Use a consistent error envelope with `details: []` for non-field failures. Known
field paths use body/query/path prefixes; never reflect unknown client field names.
See the shared error/logging contract for the reviewed disclosure boundaries.
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

- Ticket creation field rules and examples are recorded in the reviewed
  [validation contract](ticket-creation-validation.md). Identity inputs and token
  behavior are recorded in the [identity contract](identity-authentication-contract.md).
  Organization name and membership/Comment input bounds are reviewed above. Finalize
  missing target memberships, unexpected server errors, and overlapping-failure
  precedence.
- Finalize the proposed queue/directory filters, non-Ticket collection ordering,
  count/items consistency and error details conventions. Organization creation/list
  and ownership-transfer nested responses are reviewed above.
- Define same-assignee/same-role updates and repeated reactivation/deactivation
  cases without weakening current authorization.
- Implement the accepted [concurrency contract](concurrency-contract.md) for
  claims, ownership, role changes, deactivation, and reopening. It specifies a
  2-second per-lock wait, full rollback and 503 concurrency_busy for recognized
  contention failures, with no automatic retry. This is accepted behavior awaiting
  implementation; endpoint-specific no-op and overlapping-error decisions remain #3.
- Decide when the deferred Attachment table becomes an executable migration.
- Follow the [26 published issues](issue-plan.md) and their prerequisites. Publication
  does not resolve design decisions; completion needs the corresponding evidence.

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
