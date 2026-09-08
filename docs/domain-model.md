# Domain Model

Reviewed: Week 09 Tuesday, 8 September 2026.

This document consolidates Furkan's domain drafts and the mentoring review.
It records business rules, not implemented behavior. Entity fields, physical keys,
database constraints, and complete access and transition matrices remain pending.
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
In the current customer creation flow, requester and creator happen to be the same
authenticated User. Creating Tickets on behalf of other Users is outside that flow.

## User

**Purpose and identity:** A global individual account with a stable identifier.
Email, password, and profile changes do not change that identity.

**Relationships:** Zero or more OrganizationMembership records. Ticket and Comment
attribution refers to this identity; the physical relationship keys are not chosen
yet. A User's current membership determines access, not historical authorship alone.

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
boundaries follow their parent Ticket; this does not yet prescribe duplicate
organization columns in every table.

**Lifecycle:** Created through an authorized workflow. Exact creation, suspension,
archival, deletion, and retention workflows remain to be designed.

**Rules:**

- O-01: Membership or authority in one Organization grants no access to another
  Organization's resources. A User may independently belong to both.
- O-02: An active Organization has exactly one active owner membership belonging
  to an active User. An admin remaining in the Organization does not replace this
  ownership requirement.
- O-03: Ownership transfer to an eligible active member is atomic. On success the
  new member is owner and the previous owner is admin. On failure neither role
  change is committed. Exact caller permissions remain in the matrix backlog.
- O-04: Removing, deactivating, or demoting the owner cannot leave an active
  Organization without its required owner. Transfer ownership first.

The single-owner policy provides clear responsibility and a bounded transfer model.
It does not depend on billing features. Atomicity does not mean every internal SQL
statement simultaneously updates both memberships. Constraint timing and concurrent
transfer handling must be designed before implementation.

## OrganizationMembership

**Purpose and identity:** The contextual relationship between exactly one User and
one Organization. The User-Organization pair is unique across all membership states;
the eventual primary-key representation remains a relational-design decision.

**Lifecycle:** Created through organization creation or authorized member addition.
The role may change. Departure makes the membership inactive; rejoining reactivates
the same record with an explicitly authorized current role. Invitation mechanics
remain open, and email delivery is outside Month 03.

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
  preconditions apply independently.

A stable membership preserves relationship continuity, but overwriting current role
or state does not preserve previous role/state history. A complete audit trail is a
separate capability, not something this record already provides.

## Ticket

**Purpose and identity:** A support request with a stable identifier independent of
status, priority, or current assignment.

**Relationships:** Exactly one Organization, one requester, and one creator; an
optional current assignee; zero or more Comments and Attachment metadata records.
The choice of User and/or membership foreign keys remains pending.

**Lifecycle:** Created as `open`, optionally unassigned. Status vocabulary is `open`,
`in_progress`, `resolved`, `closed`; priority vocabulary is `low`, `medium`, `high`,
`urgent`. These values alone do not authorize transitions or priority changes.

**Rules:**

- T-01: Organization, requester, and creator cannot change in the current scope.
- T-02: Creation derives requester and creator from the same current authenticated
  User. The User, target membership, and Organization must be active, and the caller
  must have Ticket-creation permission.
- T-03: A newly created Ticket is `open` and may have no assignee.
- T-04: An assignee, whenever present, belongs to the Ticket's Organization.
- T-05: Assignment requires an authorized caller and an eligible assignee. The exact
  eligible roles and assignment permissions remain to be defined; eligibility is
  not assumed to mean the `agent` role alone.
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
  unassignment by status remains a transition-matrix decision.
- Preserve the last assignee reference on `resolved` or `closed` Tickets when the
  assignee's eligibility is later revoked; it is contextual attribution, not a full
  history of past assignments.
- If reopening is supported, re-evaluate assignment eligibility before reopening.
  The exact reject, reassign, or permitted-unassignment workflow remains open.

This is an explicit-handover policy. It avoids silently stranding assigned work;
it does not guarantee timely resolution or prohibit initially unassigned Tickets.
Automatic unassignment was not selected; it would not inherently require a job queue.

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

## Attachment

**Purpose and identity:** Metadata describing a file associated with a Ticket.
Its stable identity is independent of filenames, storage paths, or physical bytes.
Candidate metadata includes filename, byte size, and MIME type (a content-type label
such as `application/pdf`); exact fields and validation limits remain pending.

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

Metadata deletion, retention, physical file cleanup, and synchronous/asynchronous
cleanup choices remain open for the future storage workflow.

## Review and Implementation Handoff

Wednesday must translate the model into keys, nullability, uniqueness, foreign keys,
and deliberate deletion behavior. Thursday must define eligible roles, object-level
visibility, privileged operations, priority permissions, and status transitions.
Comment-posting rules by Ticket status and assignment requirements for `in_progress`
remain open. Owner transfer, ordinary deactivation, and concurrent assignment changes
must preserve their shared rules; a check followed by a separate unguarded write is
not sufficient. Organization suspension and emergency account suspension behavior
require explicit future policy rather than an assumed bypass.

Future tests should cover:

- Ownership transfer success, rollback, and concurrent conflicting transfers.
- Rejoining without duplicate memberships or automatic privilege restoration.
- Inactive accounts/memberships and old tokens failing protected operations.
- Same-Organization assignment, active eligibility, and unauthorized assignment.
- Scoped versus global eligibility-revocation checks, unchanged state on rejection,
  successful deactivation after handover, and eligibility checks when reopening.
- Fixed Ticket participants, fixed Comment parent/author, append-only comments,
  and Ticket-scoped comment reading and posting.
- Attachment parent boundaries and metadata not proving file availability.

These are test expectations, not executable or passing tests. No CRUD, schema,
storage, or authorization implementation is authorized by this document alone;
the complete Week 09 implementation gate still applies.
