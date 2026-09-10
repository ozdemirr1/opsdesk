# Access-Control Matrix

Reviewed: Week 09 Thursday, 10 September 2026.

This document records Furkan's reviewed product policies. It describes expected
behavior, not implemented or tested authorization. Read it with the
[Ticket lifecycle](ticket-lifecycle.md), [domain model](domain-model.md), and
[relational model](relational-model.md). API paths and exact error contracts remain
Friday's design work.

## Shared Preconditions and Rule Composition

- The actor is the current authenticated, active User with an active membership
  in the active target Organization. Roles come from that membership, not a global
  User role or a stale token claim. Historical participation alone grants no access.
- Every identified Ticket and target membership belongs to that Organization.
  Owner permissions never cross tenant boundaries.
- An action must satisfy the relevant role/resource rule, lifecycle restriction,
  and business preconditions together. No single Allowed cell bypasses the others.
- Deny operations without an explicit applicable permission. Pending product
  workflows do not implicitly authorize new endpoints.
- Check permissions on each operation, including direct resource lookups and child
  access. Collection queries apply the visibility scope before pagination/counts.
- Authorize before mutation. Rejected operations leave business state unchanged;
  failures in a transaction must not persist partial changes.
- Actor means the person making the request. Assignment eligibility describes the
  recipient of work; these are separate checks.

## Ticket Visibility

| Action | Customer | Agent | Admin | Owner |
| --- | --- | --- | --- | --- |
| List tickets | Own requested tickets only | All tickets in the organization | All tickets in the organization | All tickets in the organization |
| Read ticket details | Own requested tickets only | All tickets in the organization | All tickets in the organization | All tickets in the organization |
| Read ticket comments | Own requested tickets only | All tickets in the organization | All tickets in the organization | All tickets in the organization |

Own requested tickets means requester_membership_id matches the actor's current
membership. Comment reads follow the parent Ticket. These scopes apply in all four
Ticket states, including closed; posting has separate restrictions.

Organization-wide agent visibility supports a shared queue, review of unassigned
requests, and handover context. It does not itself grant claiming or reassignment.

## Ticket Creation, Priority, and Commenting

| Action | Customer | Agent | Admin | Owner |
| --- | --- | --- | --- | --- |
| Create a ticket for self | Allowed | Allowed | Allowed | Allowed |
| Select priority during creation | Allowed | Allowed | Allowed | Allowed |
| Change an existing ticket's priority | Denied | Any ticket in the organization | Any ticket in the organization | Any ticket in the organization |
| Add a comment to a visible ticket | Own requested tickets only | Any ticket in the organization | Any ticket in the organization | Any ticket in the organization |

Existing-record actions also require the status-based limits in the lifecycle
document. In particular, staff may change priority in open/in_progress, and permitted
members may comment in open/in_progress/resolved. No role can comment in closed.

Creation always derives creator and requester from the same authenticated membership.
Every new Ticket starts open and unassigned; assignment at creation is denied for
all roles. The creation contract rejects client-supplied assignment fields rather
than silently applying or ignoring them. On-behalf-of creation is not supported.

Valid priorities are low, medium, high, and urgent. Omitted priority defaults to
medium. Explicit null, empty text, and unknown values are invalid, not fallback
requests. Ordinary creation cannot override the initial status or attributed identities.

Comments remain append-only for all roles. Adding a comment does not itself reopen
or otherwise change a Ticket's status. There are no staff-only internal notes.

## Assignment

| Action | Customer | Agent | Admin | Owner |
| --- | --- | --- | --- | --- |
| Claim an unassigned ticket for self | Denied | Any unassigned ticket in the organization | Any unassigned ticket in the organization | Any unassigned ticket in the organization |
| Assign an unassigned ticket to another member | Denied | Any unassigned ticket in the organization | Any unassigned ticket in the organization | Any unassigned ticket in the organization |
| Reassign an assigned ticket to another member | Denied | Only tickets currently assigned to self | Any assigned ticket in the organization | Any assigned ticket in the organization |
| Remove the current assignment | Denied | Only tickets currently assigned to self | Any assigned ticket in the organization | Any assigned ticket in the organization |

Eligible assignee roles are agent, admin, and owner. The recipient's User and
same-Organization membership must both be active. Admins/owners may handle support
work in small teams; customers are excluded by this product policy.

Claiming or assigning an unassigned Ticket occurs in open: in_progress requires an
assignee. Reassignment is permitted in open/in_progress under the actor rules above.
Ordinary removal is permitted only in open. No ordinary assignment changes are
permitted in resolved/closed. Reopening has its own conditional cleanup rule.

Agents can distribute unassigned work, but cannot take over, redirect, or remove
another member's existing assignment. Visibility does not override that restriction.

## Membership Management

Except for explicit self-service rows, another member means a different User.
Ordinary management never edits the owner membership. Every operation also preserves
the ownership and active-assignment preconditions from the domain model.

| Action | Customer | Agent | Admin | Owner |
| --- | --- | --- | --- | --- |
| Add/reactivate another member as customer/agent | Denied | Denied | Allowed | Allowed |
| Promote another customer/agent to admin | Denied | Denied | Allowed | Allowed |
| Change another customer to agent | Denied | Denied | Allowed | Allowed |
| Change another agent to customer | Denied | Denied | Allowed after active-work handover | Allowed after active-work handover |
| Change another admin to customer/agent | Denied | Denied | Allowed; customer target requires active-work handover | Allowed; customer target requires active-work handover |
| Deactivate another customer/agent | Denied | Denied | Allowed after active-work handover | Allowed after active-work handover |
| Deactivate another admin | Denied | Denied | Allowed after active-work handover | Allowed after active-work handover |
| Change own role through ordinary role update | Denied | Denied | Denied | Denied |
| Leave by deactivating own membership | Allowed | Allowed after active-work handover | Allowed after active-work handover | Denied; transfer ownership first |
| Transfer organization ownership | Denied | Denied | Denied | Allowed to an eligible recipient |

Active-work handover means no affected open/in_progress assignments may remain when
eligibility is revoked. This guard applies within the target Organization. Permitted
unassignment can also remove a blocking assignment. Other domain preconditions still
apply; a customer normally has no eligible active-work assignments.

Admin-to-agent preserves assignment eligibility and must not be rejected merely
because active-work assignments exist. Admin-to-customer revokes eligibility.
Membership deactivation always revokes it. Global account deactivation checks all
Organizations and ownership dependencies; it is not an admin membership operation.

Reactivation updates the existing inactive row with an explicitly authorized
customer/agent role. It is not an alternative route for rewriting active memberships,
editing an owner, or restoring historical privileges automatically. It never activates
a global User account. Invitation mechanics and inactive-User target handling remain
API/workflow decisions; they are not implied by the role matrix.

### Peer Management and Ownership Transfer

Admins may promote, demote, and deactivate non-owner peers to support delegated
onboarding/offboarding. This is deliberately broad authority. An admin cannot edit
the owner or transfer ownership, but protecting that boundary does not prevent all
operational disruption or misuse through a compromised admin account.

Only the current owner can transfer ownership, and only to a different, currently
active User with an active admin membership in the same Organization. Both role
changes are atomic: the recipient becomes owner and the previous owner becomes admin.
Ordinary role update cannot set owner; self-role updates cannot bypass transfer.

The admin prerequisite reduces accidental transfers to non-admin members. Promotion
is a separate authorized action that immediately grants admin permissions. The two
steps do not independently prove intent, provide a second approver, or protect against
misuse of a compromised owner account. Self-demotion is not inherently unsafe; this
product uses explicit leave and ownership-transfer workflows instead.

## Concurrency and Verification Handoff

Current-state authorization and mutation need a cooperating transaction protocol.
Two agents who both observed an unassigned Ticket must not overwrite each other's
claims. Check current assignment for handover, current roles for membership changes,
and current admin/active status at ownership transfer. Assignment, deactivation,
reopening, and ownership workflows must coordinate; separate checks plus writes are
insufficient. Exact locking, lock order, conflict responses, and retries remain open.

The [reviewed scenarios](ticket-lifecycle.md#acceptance-scenarios) are design evidence,
not executed tests. Future verification must also cover cross-tenant attempts,
inactive actors/organizations, foreign requesters, ordinary self-promotion, owner
edits through alternate operations, reactivation bypasses, concurrent claims, and
ownership/assignment races. Assert durable unchanged state after rejected mutations.

Organization creation/read/update/suspension, membership directory visibility,
global account-management endpoints, attachment-metadata operations, and Ticket
title/description editing or deletion are not defined by these matrices. Resolve
their inclusion and permissions with the endpoint inventory; do not infer blanket
admin/owner authority. Exact HTTP errors, same-value updates, validation lengths,
and pagination contracts also remain open before the full Week 09 gate is complete.

## Reference

[OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
supports explicit permissions, least privilege, per-request checks, and deny by
default. OpsDesk's specific role scopes are product decisions, not OWASP mandates.
