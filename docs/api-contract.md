# API Contract Baseline

> Implementation checkpoint: [project status — 30 October](project-status.md).
> Design inventories and historical handoff notes below are not a claim that all
> listed workflows are implemented.

Reviewed: Week 09 Friday, 11 September 2026.
Ticket read/search amendment: 26 October 2026; implemented and tested locally.
Deployment and frontend integration remain separate gates.

This document consolidates the endpoint drafts and mentoring corrections. It is a
design baseline, not an implemented API or a complete OpenAPI specification. Read
it with the [access-control matrix](access-control.md),
[Ticket lifecycle](ticket-lifecycle.md), and [requirements](requirements.md).
The finalized review and test handoff at the end supersede the original
remaining-review checklist. The Week 09 backlog is published; accepted design
does not mean every dependent endpoint is implemented.
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
storage bounds. The Organization input normalizer, strict request schema, service,
SQLAlchemy adapter, and HTTP endpoint are implemented on the Week 12 feature branch.
Guarded local PostgreSQL tests now verify committed projections from fresh Sessions,
rollback without partial records, duplicate display names, unrelated-role independence,
real lock-timeout handling, and independent-User progress. Hosted CI, review, and merge
remain required before the endpoint is considered delivered.

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

30 October checkpoint: the priority PUT subset below is implemented and tested
locally. Priority UI and publication remain pending; assignment/status operations
remain design scope.

| Purpose | Method and path | Input | Authorization and behavior | Success |
| --- | --- | --- | --- | --- |
| Create for self | `POST /organizations/{organization_id}/tickets` | title, description; optional priority | All four roles; open and unassigned; requester and creator derived from actor | 201 TicketResponse |
| List | `GET /organizations/{organization_id}/tickets` | Optional query: q, status, priority, assignment, assignee_membership_id; pagination | Customers: requested by self; staff: all in Organization | 200 paginated TicketResponse items |
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

The reviewed Ticket filters are `status=open|in_progress|resolved|closed`,
`priority=low|medium|high|urgent`, `assignment=assigned|unassigned`, and a positive
signed-bigint `assignee_membership_id`. Omission means no restriction for that field.
Combining `assignment=unassigned` with `assignee_membership_id` is contradictory and
returns `422 validation_error`; `assignment=assigned` with a specific assignee is
allowed. A syntactically valid missing or foreign assignee ID yields an empty visible
result rather than disclosing target existence. Filters are applied inside the
caller's existing visibility scope and can never widen it.

### Ticket Read Contract — 26 October 2026

Week 16 contract amendment for F11. GET list/detail and server-side search now
have a local implementation and tests; see the
[F11 checkpoint](issues/f11.md#week-16-local-implementation--26-october-2026).
This section adds title search and an explicit Ticket offset bound to the earlier
collection contract. Existing Organization and membership endpoints are unchanged.

#### Request parameters

`GET /organizations/{organization_id}/tickets` accepts only the following query
keys. Each may occur at most once, even if repeated values are identical.
All supplied filters combine with AND inside the caller's visibility scope.

| Key | Omitted value | Accepted supplied value |
| --- | --- | --- |
| `q` | No title restriction | Search text with the rules below |
| `status` | All states | `open`, `in_progress`, `resolved`, `closed` |
| `priority` | All priorities | `low`, `medium`, `high`, `urgent` |
| `assignment` | Either | `assigned`, `unassigned` |
| `assignee_membership_id` | Any assignee or none | Positive signed-bigint ID |
| `limit` | 20 | Integer 1..100 |
| `offset` | 0 | Integer 0..9223372036854775807 |

For numeric query values, accept nonempty ASCII decimal digits only (leading
zeros are allowed); reject signs, whitespace, decimals, exponent notation and
out-of-range values. Path IDs use the existing `PositiveBigInt` contract, not a
new incompatible parser. Unknown/repeated query keys, invalid enums or numbers,
and `assignment=unassigned` with an assignee ID return `422 validation_error`.
Empty enum/numeric values are invalid; `q` has its separate blank-input rule.
Do not silently clamp values. The offset upper bound prevents an otherwise
validated value exceeding PostgreSQL's signed-bigint range; it is not a practical
performance guarantee for deep pages.

`GET /organizations/{organization_id}/tickets/{ticket_id}` takes no query
parameters; reject supplied query keys with the same safe validation envelope.
Both successful endpoints return the existing public `TicketResponse` fields.
Detail returns one object; list returns the common envelope. No requester/role
selector is accepted from the client.

#### Title-search semantics

- Apply rules to the HTTP-decoded string; do not decode it a second time.
- Bound the supplied decoded value to at most 255 Unicode code points **before**
  trimming. Reject longer input, including excessive padding, with 422.
- Reject NUL, LF, CR and TAB before trimming, matching the existing title-input
  policy. Trim edges with Python `str.strip()`; preserve internal whitespace,
  punctuation and Unicode. Do not add Unicode normalization or accent removal.
- Omission, `q=` or an allowed whitespace-only value means no title restriction.
  The literal string `null` is ordinary search text, not a missing value.
- Search the title only for one contiguous substring, case-insensitively using
  PostgreSQL `ILIKE` under the title column's deterministic database collation.
  Do not search descriptions, IDs, emails or comments. Do not tokenize, rank,
  interpret regex, transliterate or promise language-independent case folding.
  Record/check the test and hosted collation before integration; Turkish dotted/
  dotless-I equivalence must not be assumed from JavaScript `toLowerCase()`.
- `%`, `_`, `!` and backslash are literal user characters. Use an explicit SQL
  escape character `!`: escape `!` first, then `%` and `_`, wrap the result in
  substring `%` delimiters, and bind the pattern as a query parameter with
  `ESCAPE '!'`. Backslash is literal with that escape choice. Never interpolate
  user text into SQL. Binding and wildcard escaping address different concerns.
- Match inside tenant/requester scope and combine with the other filters before
  calculating count and page. Do not fetch a page and search it in Python/React.
- Keep search values out of request diagnostics, SQL exception responses and
  validation output; retain existing route-template logging and safe field paths.

PostgreSQL's [pattern-matching documentation](https://www.postgresql.org/docs/18/functions-matching.html)
defines `ILIKE` locale behavior and `LIKE` escaping. This bounded search needs no
new extension or migration; it makes no indexed-search or large-dataset latency
claim. Local PostgreSQL verification on 26 October used libc `en_US.UTF-8`
(`datcollate` and `datctype`): `I ILIKE i` and `İ ILIKE i` were true, while
`ı ILIKE I` was false. The hosted collation still needs verification before
real UI integration; this is not a universal Turkish case-equivalence guarantee.

#### Access and error composition

Use the [Ticket read decision table](access-control.md#ticket-read-decision-table--26-october-2026).
After existing transport/schema handling, preserve shared business precedence:
current active User → active membership in path Organization → active Organization
→ Ticket visibility. Do not override framework validation ordering to promise
that every malformed unauthenticated request is always 401; overlapping cases
must follow the existing dependency/error contract and get API tests.

| Otherwise valid request | Result |
| --- | --- |
| Missing/invalid/expired token or missing/inactive current User | 401 `unauthenticated`, bearer header |
| Missing Organization or no active actor membership | 403 `organization_access_denied` |
| Active member, suspended Organization | 403 `organization_suspended` |
| Authorized list, no visible matching records | 200, empty `items`, `total_count: 0` |
| Authorized detail, missing/foreign/invisible Ticket | 404 `ticket_not_found`; same safe response |
| Authorized visible Ticket in any lifecycle state | 200; reading grants no write permission |

#### Ordering, count and examples

Use `created_at DESC, ticket_id DESC`; no client-controlled sort field in this
slice. All visibility/search/filter predicates must be identical for count and
items. Prefer the existing Organization repository's single-statement pattern:
visible relation → total count and ordered page → outer join from count to page.
This preserves the correct total even when the page is empty. A window count alone
cannot supply a total for an offset beyond the last row. Keep read queries free of
mutation locks and business writes. The one-response snapshot guarantee does not
promise stable offsets across different HTTP requests.

Examples below assume valid authentication and Organization access; IDs are
illustrative, not live demo resources. Local implementation follows this contract.

| Request suffix or case | Expected result |
| --- | --- |
| `/tickets` | First 20 visible records, newest first |
| `/tickets?q=%20EMAIL%20&status=open&limit=10&offset=0` | Visible open records whose titles contain `EMAIL`, ignoring case under database collation |
| `/tickets?q=%25` | Only titles containing a literal percent sign |
| `/tickets?q=release_1` | Literal underscore; does not match `releaseX1` |
| `/tickets?q=%21` or `/tickets?q=%5C` | Literal exclamation mark or backslash |
| `/tickets?q=%20%20` | No title restriction; other filters still apply |
| `/tickets?q=%09email` or a 256-code-point decoded query | 422 |
| `/tickets?q=email&q=email` or `/tickets?role=owner` | 422 |
| `/tickets?assignment=unassigned&assignee_membership_id=12` | 422 |
| Valid foreign/missing assignee ID | 200 empty visible collection, without confirming membership existence |
| 12 matching records, `limit=20&offset=20` | `items: []`, `total_count: 12`, `limit: 20`, `offset: 20` |
| Title matches another customer only | That row contributes neither an item nor a count |

No matches returns:

```json
{"items": [], "total_count": 0, "limit": 20, "offset": 0}
```

Keep UI input text separate from normalized query text; omit blank `q`, reset offset
when Organization/search/filter changes, and clear/invalidate old scope results.
Do not send mock-only `all` enum values; omission means all. Searching the real
collection must issue a server query and use server count, not the current page's
length. Debouncing or caching later must not weaken stale-response protection.

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
| Authorized actor assigns the same currently eligible assignee again | 200 | None; assignment/state rules still apply |
| Admin removes assignment from an already unassigned open Ticket | 200 | None |
| Admin/owner repeats the same permitted role for another active non-owner member | 200 | None; target and handover preconditions still apply |
| Admin/owner reactivates an already active membership | 409 state_conflict | None; reactivation does not replace role update |
| Admin/owner deactivates an already inactive non-owner membership | 200 | None; return its inactive projection |
| Former member repeats `/memberships/me` after leaving | 403 organization_access_denied | None; active membership authorization is gone |
| Former owner repeats the completed ownership transfer | 403 permission_denied | None; the actor is no longer owner |

The [same-status permission table](ticket-lifecycle.md#same-status-requests) is
distinct from visibility and real transitions. Seeing a resolved Ticket does not
authorize a customer to PUT resolved, even when that value is already stored.

HTTP idempotency concerns the intended effect of repeated requests, not identical
responses. It does not mandate returning 200 after the caller loses permission.
Repeated Comment, Organization and Ticket creation requests create distinct resources;
this release has no idempotency-key protocol. The table is endpoint-specific rather
than a universal shortcut.

## Comments and Memberships

29 October implementation checkpoint: Comment GET/POST and their service rules
are implemented and tested locally. Comment UI integration was completed locally on 30 October. Publication and
the membership mutations below remain separate work. Closed posting returns `409 state_conflict`;
hidden parents return `404 ticket_not_found`.

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

The membership directory accepts exact `role=customer|agent|admin|owner`,
`is_active=true|false`, and `assignable=true|false` filters. Omission means no
restriction for that field. Assignable means the membership is active, its global
User is active, and its role is agent/admin/owner; false selects the complement inside
the authorized directory without adding global account fields to the response.
`assignable=true` with `is_active=false` or `role=customer` is contradictory and
returns `422 validation_error`. Combining it with `is_active=true` or an eligible
staff role is allowed even though the condition is partly redundant. The assignment
operation always checks current eligibility again. Human-readable directory labels
are a separate future design.

Add/reactivate accepts customer/agent only, preserving the reviewed membership
matrix. Granting admin requires the separate authorized role update. Neither ordinary
role update nor reactivation may rewrite the owner or change the actor's own role.
Admin-to-agent preserves eligibility; active work alone does not block that change.

Membership DELETE is logical deactivation, retaining the row and historical references.
An authorized admin/owner repeating deletion of an already inactive non-owner target
receives the current inactive projection without a write. After leaving, the caller no
longer passes active membership authorization on a retry. Likewise, a former owner
cannot repeat ownership transfer using their old authority. Resolve the static
`/memberships/me` route distinctly from the numeric member route.

### Exact-email Addition and Disclosure Limits

Addition is direct membership creation for an existing active User; it is not an
email invitation, consent workflow, or account creation. Match using the same
canonical email policy as registration/login; no partial search or user directory.

Missing and inactive global Users share `400 user_not_addable`, with a safe message
such as "The specified user cannot be added." An existing membership, including an
inactive row, yields `409 membership_exists`; use the explicit reactivation workflow.
When both apply, `membership_exists` takes precedence after canonical User lookup so a
duplicate row is never treated as a new addition. Reactivating that row still requires
an active global User and otherwise returns `400 user_not_addable`.

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
| Authorized membership lookup target is missing or outside the path Organization | 404 | membership_not_found |
| Assignment target is missing, foreign, inactive, globally inactive, or has an ineligible role | 400 | assignee_not_eligible |
| Ownership-transfer target is missing, foreign, inactive, globally inactive, or is not an admin | 400 | ownership_target_not_eligible |
| Email does not identify an addable active User | 400 | user_not_addable |
| Registration uses an already registered canonical email | 409 | email_already_exists |

The new target errors use fixed messages: membership_not_found is
`Membership not found.`; assignee_not_eligible is
`The specified assignee is not eligible.`; ownership_target_not_eligible is
`The specified ownership target is not eligible.`. They use `details: []` and never
include a submitted identifier or the hidden reason for ineligibility.

Protected bearer 401 responses include `WWW-Authenticate: Bearer`. After transport and
schema validation, business checks use this precedence: current authentication;
active actor membership/Organization concealment; Organization active state for child
operations; resource scope/visibility; operation permission; current resource state;
then referenced-target eligibility. Missing/foreign/invisible Tickets share a public
response. Missing/foreign membership path targets also share one response. Assignment
and ownership targets use their generic eligibility errors rather than disclosing
which target condition failed.

This ordering means a caller who lacks operation permission receives 403 even when the
visible resource is also in a conflicting state; an authorized caller blocked only by
state receives 409. Validation that the framework completes before entering the
business handler remains 422. Recognized lock/deadlock/serialization contention can
produce the accepted 503 before a business outcome is knowable; other unexpected
infrastructure failures remain 500. Every rejected mutation rolls back and returns no
success projection.

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

## Timestamp Policy

Ticket and Comment timestamps are database-generated `timestamptz` values using
PostgreSQL `statement_timestamp()`. API responses serialize them in RFC 3339 UTC form
with `Z`; fractional seconds may contain up to PostgreSQL's six-digit microsecond
precision. Clients must not submit these fields.

Ticket creation sets `created_at` and `updated_at` from the same insertion statement.
A successful business change to Ticket priority, status, or assignment refreshes
`updated_at` in the same database statement that changes the field. A successful
no-op, rejected/rolled-back request, membership mutation, and Comment insertion do
not refresh the Ticket timestamp. Comments are append-only and have `created_at` only.

These values describe database statement time, not strict transaction commit order,
an event log, or an optimistic-lock version. Every operation still uses the accepted
locking and fresh-state checks; clients must not use timestamps as authorization or
concurrency tokens.

## Pagination and Filtering

- Use integer limit and offset. Default limit: 20; valid range: 1..100.
  Default offset: 0; minimum: 0. Reject invalid values with 422; do not silently clamp.
- Each pagination/filter key may appear at most once. Repeated keys, unknown query
  fields, invalid enums and invalid scalar representations return `422 validation_error`.
  Boolean filters accept only the lowercase query text `true` or `false`.
- Ticket ordering is created_at DESC, ticket_id DESC. The ID breaks timestamp ties;
  it does not prove commit chronology. Organization lists use organization_id ASC;
  membership lists use membership_id ASC; Comment lists use created_at ASC,
  comment_id ASC so conversations read chronologically. These ID orderings are stable
  tie-breakers, not a claim that IDs equal commit time.
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

Within one response, total_count and items must come from the same PostgreSQL snapshot.
Implementations may use one SQL statement, or two SELECTs inside one short,
read-only REPEATABLE READ transaction whose snapshot begins before either query. No row
lock is required for this read contract. A later HTTP request receives a new snapshot;
offset pagination therefore does not promise stability across requests.

`GET /organizations` accepts only `is_active=true|false` in addition to pagination;
omission includes active and suspended Organizations, always limited to Organizations
where the actor currently has an active membership. Ticket filters have the exact
semantics defined in the Tickets section. Comment lists have no filter beyond
pagination. Membership filters have the exact role/active/assignable semantics defined
in the Comments and Memberships section. A valid filter that matches nothing returns
the ordinary 200 empty collection envelope, not a resource-existence error.

## Deferred Month 03 Operations

| Operation | Scope and rationale |
| --- | --- |
| Edit Ticket title/description | No endpoint; original request remains immutable through product operations. Clarifying comments are allowed only before closed. |
| Delete Ticket | No endpoint; closed ends work but does not erase data. FKs restrict referenced parents, not every possible Ticket deletion. Retention/erasure needs separate design. |
| Rename Organization | Deferred administrative convenience. The display name is distinct from stable Organization identity. |
| Suspend/reactivate Organization through a user endpoint | Deferred actor/workflow design. Inactive state remains relevant to access checks and future test fixtures. No billing workflow is implied. |
| Globally deactivate own User | No endpoint this month. Existing cross-Organization ownership/assignment preconditions remain domain rules for future implementation. |
| Create/read/delete Attachment metadata | No metadata API this month. Domain/relational design remains; file upload/download/storage is also excluded. Metadata can have independent value, but is not required for this release's core workflow. |

The Attachment table is also excluded from the Month 03 executable Ticket migration.
Keep its domain and relational design for forward planning, then introduce its table
with the first scheduled metadata/upload feature after filename, media type, size,
authorization, retention and physical-storage failure behavior are reviewed. No empty
table is created merely to mirror a deferred entity.

Comment edit/delete, internal notes, on-behalf-of Ticket creation, refresh tokens,
email delivery, frontend, background jobs, Docker, and AI retain their existing exclusions.

## Finalized Review and Test Handoff

- Ticket creation field rules and examples are recorded in the reviewed
  [validation contract](ticket-creation-validation.md). Identity inputs and token
  behavior are recorded in the [identity contract](identity-authentication-contract.md).
  Organization name and membership/Comment input bounds, missing target behavior,
  unexpected server errors and overlapping-failure precedence are reviewed above.
- Collection filters, deterministic ordering and single-snapshot count/items behavior
  are reviewed above. Organization creation/list and ownership-transfer nested
  responses are also reviewed. Business error details and overlapping-failure
  conventions are reviewed above.
- Same-assignee/same-role updates and repeated reactivation/deactivation behavior are
  explicitly defined above without weakening current authorization.
- Implement the accepted [concurrency contract](concurrency-contract.md) for
  claims, ownership, role changes, deactivation, and reopening. It specifies a
  2-second per-lock wait, full rollback and 503 concurrency_busy for recognized
  contention failures, with no automatic retry. This is accepted behavior awaiting
  implementation; endpoint-specific no-op and overlapping-error decisions are fixed
  above and must be preserved by those implementations.
- The timestamp policy and deferred Attachment migration timing are reviewed above.
- Follow the [26 published issues](issue-plan.md) and their prerequisites. Publication
  does not resolve design decisions; completion needs the corresponding evidence.

Future tests must verify response projections, forbidden/system fields, stale-token
account checks, tenant and requester scoping, no-op authorization and unchanged
timestamps, suspended-Organization exceptions, reactivation privilege boundaries,
rollback, filtering/count consistency, paging bounds, and safe error output.
No application tests or schema changes are required for this documentation decision.
Dependent implementations must add the listed behavior and database tests.

## References

- [HTTP semantics: idempotency](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)
- [HTTP semantics: authentication challenges](https://www.rfc-editor.org/rfc/rfc9110.html#section-11.6.1)
- [OWASP authentication and error messages](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#authentication-and-error-messages)
- [PostgreSQL LIMIT and OFFSET](https://www.postgresql.org/docs/18/queries-limit.html)
- [PostgreSQL transaction isolation](https://www.postgresql.org/docs/18/transaction-iso.html)

These references explain protocol and database behavior. OpsDesk's roles, no-op
permissions, response shapes, and release boundaries remain product decisions.
