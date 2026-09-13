# Ticket Lifecycle

Reviewed: Week 09 Thursday, 10 September 2026.
Same-status contract: Friday, 11 September 2026.

These are product rules and acceptance scenarios, not implemented behavior or
passing tests. Combine them with the [access-control matrix](access-control.md).
All operations require its shared active-actor and Organization preconditions.

## State Definitions

- open: A request awaiting work or explicitly returned from another permitted state.
  It may be assigned or unassigned. Assignment alone does not start work.
- in_progress: Work is marked as underway; an eligible assignee is required.
- resolved: Support considers the issue fixed, a workaround provided, or the question
  answered. The customer may review the solution and continue commenting.
- closed: The lifecycle and conversation are finalized. Either the customer accepts
  the resolution or permitted support staff closes the request. Closed therefore
  does not by itself prove customer acceptance or satisfaction.

Creation starts open and unassigned for every role. Closed is terminal for all roles;
further support requires a new Ticket. Existing closed Tickets and their Comments
remain readable under the visibility policy.

## Transition Matrix

Own requested means the actor is the requester. Assigned to self refers to the
current assignee, evaluated before any transition effects. Staff-wide permissions
are still limited to the same Organization and all relevant preconditions.

| Transition | Customer | Agent | Admin | Owner | Additional preconditions |
| --- | --- | --- | --- | --- | --- |
| open -> in_progress | Denied | Assigned to self | Any ticket in the organization | Any ticket in the organization | Eligible current assignee required |
| open -> resolved | Denied | Assigned to self | Any ticket in the organization | Any ticket in the organization | Eligible current assignee required |
| in_progress -> resolved | Denied | Assigned to self | Any ticket in the organization | Any ticket in the organization | Eligible current assignee required |
| resolved -> closed | Own requested tickets only | Assigned to self | Any ticket in the organization | Any ticket in the organization | Current status must be resolved; historical assignee need not remain eligible |
| in_progress -> open | Denied | Assigned to self | Any ticket in the organization | Any ticket in the organization | Current status must be in_progress; apply assignment evaluation below |
| resolved -> open | Own requested tickets only | Assigned to self | Any ticket in the organization | Any ticket in the organization | Current status must be resolved; apply assignment evaluation below |
| closed -> open | Denied | Denied | Denied | Denied | Closed is terminal |

Every allowed transition requires the exact stated source status. All unlisted
state changes are denied, including open -> closed and closed -> in_progress.
Same-status requests use the explicit permission table below; they are not new
transitions. Status vocabulary CHECKs alone enforce none of these actor rules.

Open -> resolved permits first-contact resolution without first entering
in_progress, but still requires an eligible assignee. A resolved Ticket can retain
an assignee who later becomes inactive: eligibility is required to enter resolved,
not for every future moment spent in that state. Only the caller, not necessarily
the historical assignee, must remain eligible to perform an authorized closure.

## Same-Status Requests

Authenticate and verify current User, membership, active Organization, Ticket
visibility, valid input, and the permission below before returning 200. Visibility
alone is insufficient. Denied cells return permission_denied without mutation.

| Current and requested status | Customer | Agent | Admin | Owner |
| --- | --- | --- | --- | --- |
| open | Own requested tickets only | Assigned to self | Any ticket in the organization | Any ticket in the organization |
| in_progress | Denied | Assigned to self | Any ticket in the organization | Any ticket in the organization |
| resolved | Denied | Assigned to self | Any ticket in the organization | Any ticket in the organization |
| closed | Own requested tickets only | Assigned to self | Any ticket in the organization | Any ticket in the organization |

An authorized no-op returns the current TicketResponse without updating timestamps
or applying transition effects. It does not clear a historical assignee, and does
not require that historical assignee to be eligible simply to remain resolved/closed.
Closed -> closed does not authorize any outgoing transition from closed.

These are explicit product permissions. HTTP idempotency does not require a 200
response for an actor who lacks current permission. Other repeated operations use
the [API contract](api-contract.md#repeated-requests-and-no-ops).

## Assignment Effects When Returning to Open

After authorizing the actor against current Ticket state, evaluate the existing
assignee when moving from resolved/in_progress to open:

- If there is no assignee, preserve NULL.
- If the assignee is eligible, preserve the existing assignment.
- If the assignee is no longer eligible, clear assignee_membership_id to NULL as
  part of the same transaction that changes the status to open.

Eligibility means an active User with an active same-Organization membership whose
role is agent, admin, or owner. Check current state, not a prior eligibility result.
In a valid in_progress state the assignee is eligible; ordinary eligibility-revoking
operations are blocked while such work remains assigned.

An authorized customer can trigger conditional cleanup by reopening their resolved
Ticket. This does not grant ordinary assignment permission, allow selection of a
replacement assignee, or allow removal of an eligible assignee through reopening.
The transition and its conditional cleanup succeed together or roll back together.

This synchronous rule is triggered by an authorized return to open. It does not
clear assignments when an account or membership is deactivated. Clearing the column
removes the previous current-assignee reference; this schema has no full assignment
history. Requester/creator references remain unchanged.

## Status-Based Operation Limits

These restrictions are additional to the actor/resource rules, not independent
permission grants. Allowed means allowed only if those other rules also pass.

| Action | open | in_progress | resolved | closed |
| --- | --- | --- | --- | --- |
| Add a comment | Allowed | Allowed | Allowed | Denied |
| Change priority | Allowed | Allowed | Denied | Denied |
| Assign or reassign | Allowed | Allowed; eligible assignee required | Denied | Denied |
| Remove assignment through the ordinary assignment operation | Allowed | Denied | Denied | Denied |

In_progress reassignment replaces an eligible member with another eligible member;
it does not leave the Ticket unassigned. An unassigned in_progress Ticket is not a
valid claiming opportunity. Adding a Comment to resolved does not reopen it.

To release in_progress work to the shared unassigned queue, first perform the
authorized in_progress -> open transition, which preserves an eligible assignee,
then separately request authorized unassignment. Each request rechecks current
permissions and state. If the second request fails, open-and-assigned is a valid
result; two separate requests do not form one atomic operation.

## Acceptance Scenarios

Furkan authored the four scenarios below after reviewing the matrices. This shared
background makes the active Organization/membership assumptions explicit. A rejected
mutation must leave durable business data unchanged. The [API baseline](api-contract.md)
records HTTP outcomes; executable integration tests remain future work.

```gherkin
Feature: Organization-scoped ticket lifecycle and membership rules
  Background:
    Given the target organization is active
    And the actor is authenticated with an active User account
    And the actor has an active membership in the target organization
    And all referenced tickets and memberships belong to that organization

  Scenario: Customer reopens a resolved ticket where the previous assignee is ineligible
    Given the actor is a customer with a "resolved" ticket they requested
    And the ticket's previous assignee has an inactive membership
    When the customer requests to reopen the ticket
    Then the operation succeeds
    And the ticket status changes to "open"
    And the ticket's assignee_membership_id becomes NULL
    And the requester and creator remain unchanged

  Scenario: Agent cannot reassign another member's in-progress ticket
    Given the actor is an agent
    And an "in_progress" ticket is assigned to a different eligible member
    When the agent requests to reassign the ticket to another eligible member
    Then the operation is rejected
    And the ticket remains "in_progress"
    And the current assignee remains unchanged

  Scenario: Admin with active assignments is changed to agent role
    Given the actor is the owner
    And another member is an active admin with an active User account
    And the admin is currently assigned to "in_progress" tickets
    When the owner requests to change the admin's role to "agent"
    Then the operation succeeds
    And the target member's role becomes "agent"
    And the target member's active ticket assignments remain unchanged

  Scenario: Customer cannot add a comment to a closed ticket
    Given the actor is a customer viewing their own "closed" ticket
    When the customer submits an otherwise valid new comment
    Then the operation is rejected
    And no new comment record is created
    And the ticket remains "closed"
```

Future tests must additionally cover preserving an eligible assignee on reopening,
rollback of combined status/assignment changes, membership-deactivation races,
forbidden direct unassignment in in_progress, terminal-state transitions, and every
permitted/denied role scope. These scenarios do not replace tenant-boundary tests or
prove that the authorization implementation is complete.
