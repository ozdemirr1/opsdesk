# Product Requirements

Status: Initial scope draft, reviewed during Month 03 / Week 09.
Detailed domain and authorization design remains in progress.

The [domain model](domain-model.md) records the reviewed Week 09 Tuesday
decisions. The [relational model](relational-model.md) and [ERD](erd.md) record
Wednesday's table and relationship design. Thursday's [access-control matrix](access-control.md)
and [Ticket lifecycle](ticket-lifecycle.md) define reviewed permissions and transitions.
Friday's [API contract baseline](api-contract.md) records endpoints, public errors,
pagination, and release boundaries. Its remaining-review list precedes implementation.

## Problem

Support requests tracked through scattered messages are difficult to follow.
Customers lack visibility into progress, while support teams struggle to track
responsibility, conversations, and resolution status.

OpsDesk provides a shared support-ticket system for multiple organizations.
Each organization's support data must remain isolated, and actions within an
organization must follow explicit membership and permission rules.

## Target Users

- Customer: submits support requests and follows permitted tickets.
- Agent: handles permitted tickets and communicates with customers.
- Admin: manages support operations and permitted membership actions within
  an organization.
- Owner: holds organization ownership and manages ownership-level actions.

A User is a global identity. Roles belong to OrganizationMembership. The same
User may hold different roles in different organizations. Exact permissions are
defined in the access-control matrix and its API-specific extensions.

## Primary Workflow

1. An authenticated customer selects an organization in which they have an
   active membership and submits a support request.
2. The system creates the ticket with the initial status `open` and records its
   organization and requester. The requester comes from authenticated identity.
3. An authorized organization member assigns the ticket to an eligible support
   member of the same organization.
4. The customer and support staff communicate through permitted comments.
5. Authorized members move the ticket through the defined lifecycle using
   `open`, `in_progress`, `resolved`, and `closed`.

The matrices define the allowed transitions and assignment permissions. Every role
can create a Ticket for self; creation starts open and unassigned, with medium
priority when omitted. Assignment is always a separate authorized operation.

## Functional Requirements

- **FR-01:** Users can register, log in, and access their current identity.
- **FR-02:** Authorized users can create organizations and manage memberships
  according to explicit organization-scoped permissions.
- **FR-03:** Customers with active membership can create tickets in their
  organization and view tickets permitted by the access policy.
- **FR-04:** Authorized members can assign tickets and change their status
  according to assignment and lifecycle rules.
- **FR-05:** Members can add and read comments only where the ticket and comment
  visibility rules permit access.
- **FR-06:** The domain and relational design includes Ticket-bound attachment
  metadata. Metadata create/read/delete endpoints and physical file operations
  are deferred beyond Month 03; this is not a promised release capability.

## Non-functional Requirement

Organization isolation and authorization must be enforced by the backend for
every protected operation.

Membership in one organization must not grant access to another organization's
data. Membership alone must not grant unrestricted access within an organization.

Automated tests must cover cross-organization access attempts and unauthorized
actions within the same organization. Rejected mutations must leave stored data
unchanged.

## Non-goals for Month 03

- AI summarization, priority suggestions, and category suggestions.
- React/TypeScript frontend panels and dashboards.
- Redis caching, background jobs, and email notifications.
- Docker and Docker Compose setup.
- File-content upload, download, and object storage.
- Refresh tokens, MFA, billing, and enterprise SSO.
- User-facing comment editing/deletion and staff-only internal notes.
- Attachment-to-Comment relationships and all attachment-metadata API operations.
- Ticket title/description editing and Ticket deletion.
- Organization renaming and user-facing suspension/reactivation.
- Global User deactivation endpoints. Existing deactivation invariants remain valid.

See the [scope rationale](api-contract.md#deferred-month-03-operations). Closing a
Ticket is not erasure, and FKs only restrict deletion while relevant references exist.

## Acceptance Scenarios

These scenarios specify expected behavior; they are not executable tests yet.

### AC-01: Successful Ticket Creation by an Active Customer

```gherkin
Given an authenticated user with an active customer membership in Organization A
When the customer submits a valid ticket creation request for Organization A
Then the API returns HTTP 201 Created
And the stored ticket has the initial status "open"
And the stored ticket belongs to Organization A
And the requester is derived from the authenticated user
```

### AC-02: Rejected Ticket Creation Across Organization Boundaries

```gherkin
Given an authenticated user with an active membership only in Organization A
When the user attempts to create a ticket in Organization B
Then the API returns HTTP 403 with code "organization_access_denied"
And no new ticket is persisted
```

The [error contract](api-contract.md#error-contract) uses the same organization-access
response when no active membership exists, including a nonexistent Organization.

### AC-03: Customer Cannot Resolve a Ticket

```gherkin
Given an authenticated user with an active customer membership
And a ticket in that organization that the customer is permitted to view
When the customer attempts to change the ticket status to "resolved"
Then the API returns HTTP 403 Forbidden
And the stored ticket status remains unchanged
```

The reviewed matrices confirm this restriction. HTTP 403 is the existing intended
response for this visible-resource scenario, including a same-status resolved request.
The [API baseline](api-contract.md) records the broader error contract. Additional
Thursday scenarios are recorded in the
[Ticket lifecycle](ticket-lifecycle.md#acceptance-scenarios).

## Reviewed Domain Policies

- An active Organization has exactly one active owner membership belonging to
  an active User. Ownership transfer is atomic; the previous owner becomes admin.
- Each User-Organization pair has at most one membership record across all states.
  Rejoining reactivates that record with an explicitly authorized current role.
- A User cannot be deactivated while owning an active Organization.
- The self-service creation flow derives both requester and creator from the
  authenticated User. All four roles can create for self. A Ticket's Organization,
  requester, and creator do not change.
- New Tickets are always `open` and unassigned. Assignment is a separate operation
  requiring an active User and active same-Organization agent/admin/owner membership.
- Eligibility-revoking changes are rejected while affected `open` or `in_progress`
  Tickets remain assigned. Membership/role changes are scoped to that Organization;
  global account deactivation checks all Organizations. Returning to open preserves
  an eligible assignee and clears an ineligible one atomically with the transition.
  Closed is terminal for all roles. See the lifecycle document for exact rules.
- Comments are append-only for every user role; reading follows Ticket visibility.
  Posting is allowed under role/resource rules in open/in_progress/resolved, never closed.
- Customers see their own requested Tickets; staff see all Tickets in their Organization.
- Admins may manage non-owner peers. Ordinary self-role changes are denied. Only the
  owner can transfer ownership to another active User with an active admin membership.
- Each Attachment metadata record belongs directly to exactly one fixed Ticket.

## Open Design Decisions

- Resolve the [remaining API review](api-contract.md#remaining-review-and-test-handoff):
  precise validation, email canonicalization, remaining response/error cases, query
  extensions, collection ordering, and count/items consistency.
- Define the cooperating concurrency protocol for ownership, assignment, reopening,
  and eligibility-revoking operations, including lock order and retry behavior.
- Keep deferred retention, anonymization, erasure, and storage workflows separate
  from the Month 03 endpoint inventory. No blanket administrative bypass is implied.
- Complete the prioritized issue backlog and implementation sequence.

## Implementation Gate

Review requirements, domain vocabulary and invariants, the relational ERD,
access-control and status-transition matrices, endpoint inventory, and prioritized
GitHub issues before starting CRUD implementation.

Do not copy the Month 02 Ticket API into OpsDesk. The product begins with its own
domain decisions and implementation. Add minimal CI when executable code and
meaningful tests exist. The Month 03 delivery plan includes an early deployed
backend preview; Docker remains scheduled for Month 05.
