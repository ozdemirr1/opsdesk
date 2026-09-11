# Domain Model

Domain reviewed: Week 09 Tuesday, 8 September 2026.
Relational handoff: Wednesday, 9 September 2026.
Authorization and lifecycle review: Thursday, 10 September 2026.

This document consolidates Furkan's domain drafts and the mentoring review.
It records business rules, not implemented behavior. The [relational model](relational-model.md)
and [ERD](erd.md) now describe the proposed fields, physical keys, and database
constraints. The [access-control matrix](access-control.md) and
[Ticket lifecycle](ticket-lifecycle.md) record reviewed permissions and transitions.
The [API baseline](api-contract.md) records Friday's endpoint scope and contracts,
including explicit remaining validation and workflow details.
The [product requirements](requirements.md) define the surrounding scope.

## Shared Vocabulary

| Term | Meaning |
| --- | --- |
| Domain | The business area: organization-scoped support-request management. |
| Entity | A concept tracked by stable identity while its attributes change. |
| Invariant | A rule that must hold in the relevant valid business states. |
| Precondition | A condition required before an operation may succeed. |
| Lifecycle | How an entity begins, changes, and becomes inactive or ends. |
| Tenant | An Organization's data and authorization boundary. |
| Organization owner | The membership holding ultimate organization ownership. |
| Requester | The person for whom support is requested. |
| Creator | The User who submitted the Ticket record. |
| Assignee | The support member currently assigned to handle a Ticket. |
| Author | The User who submitted a Comment. |
| Uploader | The User initiating a future attachment submission; not proof of upload success. |
| Eligible assignee | An active User with active same-Organization membership and an eligible role. |
| Active-work Ticket | A Ticket in `open` or `in_progress`, for the assignment-handover policy. |
| Metadata | Information describing a file and its relationships, distinct from file bytes. |
| Append-only | Existing comments cannot be edited or deleted through user operations. |
| Atomic operation | Changes succeed together or none are committed. |

Organization owner, requester, creator, and assignee are distinct concepts.
In the self-service creation flow for all four roles, requester and creator are the
same authenticated User. Creating Tickets on behalf of other Users is outside scope.

## User

**Purpose and identity:** A global individual account with a stable identifier.
Email, password, and profile changes do not change that identity.

**Relationships:** Zero or more OrganizationMembership records. Ticket and Comment
attribution reaches this identity through stable membership references. Current
account, membership, and resource permissions determine access, not historical authorship alone.

**Lifecycle:** Created at registration; account details can change; the account may
become inactive after the applicable preconditions succeed. Permanent deletion and
anonymization remain open decisions.

**Rules:**

- U-01: Email uniqueness is evaluated using the defined normalization policy.
- U-02: An inactive User cannot obtain an access token or perform authenticated
  operations, including with an already-issued token. Load current persisted User
  state after validating the token; a valid subject alone is insufficient.
- U-03: Roles belong to memberships, not to the global User.
- U-04: Global account deactivation is rejected while the User owns any active
  Organization or remains assigned to any active-work Ticket in any Organization.

## Organization

**Purpose and identity:** A company or tenant with a stable identifier that survives
name or settings changes.

**Relationships:** Contains memberships and owns Tickets. Comment and Attachment
boundaries follow their parent Ticket. The relational design repeats organization_id
in child tables and enforces consistency through composite foreign keys.

**Lifecycle:** Any active authenticated User may create an active Organization and
its initial owner membership atomically. User-facing renaming and suspension/
reactivation are deferred beyond Month 03; archival, deletion, and retention remain
future design. Active members can read basic suspended-Organization information,
but cannot access its child resources or perform scoped mutations.

**Rules:**

- O-01: Membership or authority in one Organization grants no access to another
  Organization's resources. A User may independently belong to both.
- O-02: An active Organization has exactly one active owner membership belonging
  to an active User. An admin remaining in the Organization does not replace this
  ownership requirement.
- O-03: Only the current owner can transfer ownership to a different active User
  with an active admin membership in the same Organization. The transfer is atomic:
  the target becomes owner and the previous owner becomes admin. On failure neither
  role change is committed.
- O-04: Removing, deactivating, or demoting the owner cannot leave an active
  Organization without its required owner. Transfer ownership first.

The single-owner policy provides clear responsibility and a bounded transfer model.
It does not depend on billing features. Atomicity does not mean every internal SQL
statement simultaneously updates both memberships. Constraint timing and concurrent
transfer handling must be designed before implementation.

## OrganizationMembership

**Purpose and identity:** The contextual relationship between exactly one User and
one Organization. The User-Organization pair is unique across all membership states;
the relational design uses a separate bigint membership_id primary key and a
User-Organization unique constraint.

**Lifecycle:** Created through organization creation or authorized member addition.
The role may change. Departure makes the membership inactive; rejoining reactivates
the same record with an explicitly authorized current role. Direct addition uses
the exact canonical email of an existing active User. Add/reactivate grants only
customer/agent; admin promotion is separate. Email invitations are outside Month 03.

**Rules:**

- M-01: At most one membership record exists per User-Organization pair, including
  inactive records.
- M-02: A membership has exactly one role from `owner`, `admin`, `agent`, `customer`.
- M-03: Its User and Organization cannot change.
- M-04: Inactive membership grants no access within that Organization.
- M-05: Reactivation does not automatically restore old privileges. The current role
  must be explicitly authorized under the membership-management policy.
- M-06: Deactivation or a role change that removes assignment eligibility is rejected
  while the membership holds active-work Tickets in that Organization. Ownership
  preconditions apply independently. Admin-to-agent preserves eligibility.
- M-07: Admin and owner can manage other non-owner memberships under the matrix,
  including admin peers. Ordinary self-role updates are denied for every role.
  Non-owners may leave after applicable handover; owners must transfer first.

A stable membership preserves relationship continuity, but overwriting current role
or state does not preserve previous role/state history. A complete audit trail is a
separate capability, not something this record already provides.

## Ticket

**Purpose and identity:** A support request with a stable identifier independent of
status, priority, or current assignment.

**Relationships:** Exactly one Organization, one requester, and one creator; an
optional current assignee; zero or more Comments and Attachment metadata records.
The relational design references memberships with the Ticket's organization_id
included in each participant foreign key.

**Lifecycle:** Always created as `open` and unassigned; assignment is separate.
Status vocabulary is `open`, `in_progress`, `resolved`, `closed`; priority vocabulary
is `low`, `medium`, `high`, `urgent`, with `medium` when omitted. In-progress work
requires an eligible assignee; closed is terminal. See the lifecycle matrix for
exact transitions and the access matrix for role/resource scopes.

**Rules:**

- T-01: Organization, requester, and creator cannot change in the current scope.
- T-02: Creation derives requester and creator from the same current authenticated
  User. The User, target membership, and Organization must be active, and the caller
  must have Ticket-creation permission.
- T-03: A newly created Ticket is always `open` and has no assignee, for all roles.
- T-04: An assignee, whenever present, belongs to the Ticket's Organization.
- T-05: Assignment requires an authorized caller and an active User with an active
  same-Organization membership whose role is agent, admin, or owner. The assignment
  matrix and status limits apply together; visibility is not assignment authority.
- T-06: Account or membership deactivation does not erase the Ticket or rewrite its
  requester/creator. Historical attribution does not grant current access.
- T-07: Current assignment may change or be removed through authorized operations
  allowed by the lifecycle policy. It does not represent complete assignment history.
- T-08: Eligibility-revoking changes must respect the active-assignment policy below.

### Active-Assignment Policy

Reject an operation that removes assignment eligibility while affected `open` or
`in_progress` Tickets remain assigned:

- Membership deactivation or an ineligible role change checks that Organization.
- Global account deactivation checks all Organizations, as well as ownership rules.
- Authorized staff must first hand over the work to eligible members. Permitted
  unassignment is limited to open Tickets under the assignment matrix.
- Preserve the last assignee reference on `resolved` or `closed` Tickets when the
  assignee's eligibility is later revoked; it is contextual attribution, not a full
  history of past assignments.
- Returning from resolved/in_progress to open re-evaluates assignment eligibility.
  Preserve an eligible assignee (or an existing NULL); clear an ineligible assignee
  atomically with the authorized transition. Closed Tickets cannot reopen. Clearing
  the current assignee does not preserve a full previous-assignment history.

This is an explicit-handover policy. It avoids silently stranding assigned work;
it does not guarantee timely resolution or prohibit initially unassigned Tickets.
Automatic unassignment on deactivation was not selected; it would not inherently
require a job queue. Conditional cleanup when returning to open is a separate rule.

**Example:** Ece has two `in_progress` Tickets in Organization A. An authorized
administrator attempts membership deactivation. The request is rejected and both
membership and Tickets remain unchanged. The administrator reassigns both Tickets
to eligible member Mehmet, then retries. Deactivation succeeds if all other
preconditions hold. Assignments in Organization B do not block this A-only change;
they do matter for global account deactivation.

## Comment

**Purpose and identity:** A conversational message or troubleshooting note with a
stable identifier, belonging to exactly one Ticket and one author.

**Lifecycle:** Created when an authorized User posts to a Ticket. The Month 03
timeline is append-only for all user roles, including admin and owner. Retention,
anonymization, and organization-wide deletion remain separate open policies.

**Rules:**

- C-01: The parent Ticket and author cannot change, including moves between Tickets
  in the same Organization.
- C-02: The organizational boundary follows the parent Ticket.
- C-03: At creation, derive author from the current authenticated User. The User,
  membership, and Organization must be active. Require both Ticket visibility and
  permission to post a Comment; these are separate checks.
- C-04: Account or membership deactivation preserves existing Comments and author
  attribution without granting continued access.
- C-05: User-facing editing and deletion are not supported. Corrections are new
  Comments rather than rewrites of old ones.
- C-06: Reading follows the parent Ticket's visibility. Staff-only internal notes
  are outside Month 03. Ticket visibility does not mean public internet visibility.
- C-07: Posting requires open/in_progress/resolved status in addition to actor and
  resource permissions. Closed comments remain readable; no new comments are allowed.
  Posting a comment never automatically reopens the Ticket.

## Attachment

**Purpose and identity:** Metadata describing a file associated with a Ticket.
Its stable identity is independent of filenames, storage paths, or physical bytes.
Candidate metadata includes filename, byte size, and MIME type (a content-type label
such as `application/pdf`). The relational model records the initial field set;
validation limits and upload behavior remain pending.

**Relationships:** Exactly one fixed parent Ticket; attribution to the User who
initiates the future attachment submission. There is no Comment relationship.

**Lifecycle:** Creation, availability, and deletion behavior will be specified with
the future file-storage workflow. Month 03 designs metadata and relationships without
implementing upload, claiming file availability, or choosing a storage provider.

**Rules:**

- A-01: An Attachment belongs directly to exactly one Ticket, and that parent cannot
  change. Its organizational boundary follows that Ticket.
- A-02: Metadata existence does not prove upload success, physical file existence,
  verified file type, or current availability.
- A-03: Attribution to the submitting User is historical and survives membership
  deactivation; it does not grant current access to the Attachment.
- A-04: Client-supplied filename, size, or MIME type is untrusted input, not verified
  evidence about file bytes. Future file inspection is outside this design phase.

All Attachment metadata API operations are deferred beyond Month 03. This entity
remains part of the domain and relational design, not a promised release endpoint.
Metadata deletion, retention, and physical file cleanup remain future workflow design.

## Review and Implementation Handoff

The relational model and ERD define proposed keys, nullability, uniqueness, and
restricted parent deletion. The reviewed access and lifecycle matrices now define
Ticket visibility, priority permissions, eligible assignees, assignment changes,
Comment posting, membership management, and ownership transfer.

The API baseline records endpoint scope, errors, pagination, and selected no-op
permissions. Exact validation, remaining response/error cases, and concurrency
details still require review. Ticket title/description edits and deletion, global
User deactivation, Organization renaming/suspension, and metadata APIs are deferred.
The original Ticket text remains fixed through Month 03 product operations.
Ownership, ordinary deactivation, assignment, and reopening must
coordinate under a transaction protocol; locking details remain pending. No reviewed
matrix implies an administrative bypass for an undesigned workflow.

Future tests should cover:

- Ownership transfer success, rollback, and concurrent conflicting transfers.
- Rejoining without duplicate memberships or automatic privilege restoration.
- Inactive accounts/memberships and old tokens failing protected operations.
- Same-Organization assignment, active eligibility, and unauthorized assignment.
- Scoped versus global eligibility-revocation checks, unchanged state on rejection,
  successful deactivation after handover, and eligibility checks when reopening.
- Fixed Ticket participants, fixed Comment parent/author, append-only comments,
  and Ticket-scoped comment reading and posting across lifecycle states.
- Attachment parent boundaries and metadata not proving file availability.

These are test expectations, not executable or passing tests. No CRUD, schema,
storage, or authorization implementation is authorized by this document alone;
the complete Week 09 implementation gate still applies.
