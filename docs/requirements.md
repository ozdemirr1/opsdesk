# Product Requirements

Status: Initial scope draft, reviewed during Month 03 / Week 09.
Detailed domain and authorization design remains in progress.

The [domain model](domain-model.md) records the reviewed Week 09 Tuesday
decisions. Detailed relational and access-control design remains pending.

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
User may hold different roles in different organizations. Exact permissions will
be defined in the access-control matrix.

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

This workflow does not authorize every transition between these statuses.
Assignment permissions, priority selection, and allowed status transitions remain
design decisions to resolve during Week 09.

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
- **FR-06:** The domain design includes attachment metadata and its relationship
  to tickets. File upload and storage are excluded. Metadata fields and permitted
  operations will be specified during domain and API design.

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
- Attachment-to-Comment relationships.

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
Then the API rejects the request
And no new ticket is persisted
```

The exact rejection status and public error response will be defined in the
authorization and API contracts.

### AC-03: Customer Cannot Resolve a Ticket — Proposed Policy

```gherkin
Given an authenticated user with an active customer membership
And a ticket in that organization that the customer is permitted to view
When the customer attempts to change the ticket status to "resolved"
Then the API returns HTTP 403 Forbidden
And the stored ticket status remains unchanged
```

This proposed restriction will be reviewed in the access-control and
status-transition matrices before implementation.

## Reviewed Domain Policies

- An active Organization has exactly one active owner membership belonging to
  an active User. Ownership transfer is atomic; the previous owner becomes admin.
- Each User-Organization pair has at most one membership record across all states.
  Rejoining reactivates that record with an explicitly authorized current role.
- A User cannot be deactivated while owning an active Organization.
- The current customer creation flow derives both requester and creator from the
  authenticated User. A Ticket's Organization, requester, and creator do not change.
- New Tickets are `open` and may be unassigned. Assignment requires an active User,
  active same-Organization membership, and a role eligible under the future matrix.
- Eligibility-revoking changes are rejected while affected `open` or `in_progress`
  Tickets remain assigned. Membership/role changes are scoped to that Organization;
  global account deactivation checks all Organizations. Reopening requires renewed
  eligibility evaluation. See the domain model for details and examples.
- Comments are append-only for every user role; reading follows Ticket visibility.
- Each Attachment metadata record belongs directly to exactly one fixed Ticket.

## Open Design Decisions

- Organization creation, invitation/addition, suspension, and archival workflows.
- Exact membership-management and ownership-transfer permissions.
- Exact permissions for owner, admin, agent, and customer.
- Ticket visibility and physical keys for participant relationships.
- Assignment eligibility and assignment permissions.
- Priority selection and modification permissions.
- Valid status transitions, including resolution, closure, reopening, and whether
  `in_progress` requires an assignee. Reopening with an ineligible previous assignee
  must have an explicit reject, reassign, or permitted-unassignment policy.
- Comment-posting permissions by Ticket status and attachment metadata lifecycle.
- Entity fields, relational constraints, and deletion behavior.
- Endpoint inventory, public errors, and pagination contracts.

## Implementation Gate

Review requirements, domain vocabulary and invariants, the relational ERD,
access-control and status-transition matrices, endpoint inventory, and prioritized
GitHub issues before starting CRUD implementation.

Do not copy the Month 02 Ticket API into OpsDesk. The product begins with its own
domain decisions and implementation. Add minimal CI when executable code and
meaningful tests exist. The Month 03 delivery plan includes an early deployed
backend preview; Docker remains scheduled for Month 05.
