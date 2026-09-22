# Coordinated transaction and concurrency contract

Drafted: 21 September 2026. Acceptance recorded: 22 September 2026. Design issue: #4.

Accepted with Furkan: cooperating Organization row locking, the lock order below,
a 2-second per-lock wait limit, fixed 503 concurrency_busy, and no automatic retry.
This is a design contract. Executable locks, contention mapping, metrics and business
concurrency tests remain implementation work; GitHub closure/merge is not claimed.

## Transaction boundary and scope

The application service owns one explicit transaction per mutation. Repositories
do not commit independently. Commit only after authorization, invariant checks,
and writes succeed; roll back the complete transaction on failure.

Every existing-Organization mutation participates: membership addition/reactivation,
role changes/deactivation/self-leave, ownership transfer, Ticket creation, assignment,
claim/reassignment/unassignment, priority/status changes, and Comment creation.
Future Organization suspension or other writes affecting these rules must join the
protocol before release. There are no new endpoints in this design change.

Do input parsing and expensive password hashing outside the locked transaction.
Do not call AI services, send email, or perform external network work while holding
locks. Normal snapshot reads need not take the Organization write lock; they still
require authorization and tenant-scoped queries.

## Lock order and fresh validation

Use READ COMMITTED isolation for this protocol:

1. Lock the target Organization with SELECT FOR UPDATE. This is the common
   coordination row, not an automatic lock on every child table.
2. Discover the relevant actor/target/current-assignee User IDs from the now-stable
   Organization state. Lock these User rows FOR SHARE, in ascending user_id order.
   Include every User whose active state is relied upon by this mutation.
3. Lock relevant OrganizationMembership rows FOR UPDATE in ascending membership_id
   order, then existing Ticket rows FOR UPDATE in ascending ticket_id order.
4. Read current values again and validate Organization activity, actor activity,
   membership/role, resource scope, target eligibility, and lifecycle preconditions.
   Previously loaded ORM objects and token role claims are not fresh evidence.
5. Perform writes, flush where necessary, and commit. All locks last until the
   transaction ends. No business writes or pending-object autoflush precede checks.

FOR SHARE allows cooperating mutations in different Organizations to share a User
lock, while blocking an update of that User's active state. FOR KEY SHARE is too
weak for this purpose because it permits non-key updates. Avoid promoting a held
User share lock to a write lock within an Organization workflow.

Current operations affect one Organization. Future multi-Organization mutations
must define their full lock set and order before implementation; do not introduce
an ad hoc nested transaction that reverses this order.

Global User deactivation remains deferred. Its implementation is gated on a reviewed
protocol coordinating with these User locks and checking ownership/active assignments
across Organizations. It must not acquire Organization locks after an exclusive User
lock, which would invert this order. This document does not implement or finish the
future global lifecycle workflow.

## New rows and constraint conflicts

Organization creation has no existing Organization row to lock. Lock the actor User
FOR SHARE, check activity, then create the Organization and its owner membership in
one transaction. Do not subsequently acquire locks on existing Organizations in this
creation transaction. Reject/roll back without leaving an ownerless Organization.

Registration uses the canonical-email unique constraint as the race arbiter: a
pre-query cannot lock an absent User. Translate only the known email uniqueness
violation to email_already_exists after rollback. Unknown database failures remain
unexpected errors; do not classify every IntegrityError as a business conflict.

New memberships and Tickets are protected by the parent Organization protocol plus
their database constraints. No attempt is made to row-lock a child that does not exist.

## Ownership transfer and representative interleavings

After acquiring locks, confirm that the actor is still the owner and the recipient
is a different active User with an active admin membership in this Organization.
Demote the old owner to admin and flush that update before promoting the new owner;
this respects the immediate partial unique index. Both writes commit together.
An intermediate zero-owner state must never commit. An injected failure between
the writes must roll back both changes.

- Two claims: the second request rechecks the assignment after waiting. It must not
  overwrite the first claimant based on its earlier unassigned observation. Apply
  the endpoint's reviewed permission/no-op/conflict rules to the new state.
- Two transfers by the former owner: after the first commits, the second rechecks
  the actor's role and is denied; it cannot execute on stale ownership authority.
- Role revocation versus assignment: if assignment commits first, the revocation
  checks active work and is rejected where handover is required. If revocation
  commits first, assignment sees an ineligible target and is rejected.
- Close versus Comment: if closure commits first, the Comment is rejected. If the
  Comment commits first, closure may follow; the previously valid Comment remains.
- Reopen versus eligibility revocation: evaluate the current assignee under the
  same protocol and atomically clear an ineligible assignee when reopening, as the
  existing lifecycle contract requires.

## Accepted wait and error policy

Set transaction-local lock_timeout to 2 seconds before lock acquisition. This is a
limit for each lock wait, not a total request deadline or a measured capacity target.
Keep transactions short; do not claim that this alone bounds all SQL execution.

For recognized PostgreSQL lock timeout (55P03), deadlock (40P01), or serialization
failure (40001), roll back fully and return a fixed 503 concurrency_busy response:
"The operation is temporarily busy. Please try again."
Do not expose database messages, SQL, parameters, or lock targets.

Initially perform no automatic retries. In particular, never blindly replay a
mutation after a connection failure with an uncertain commit outcome. A future
retry feature needs a separate bounded/idempotency design. A freshly observed
business conflict uses the existing endpoint contract, not concurrency_busy.

The public code is accepted but is not yet present in the executable error catalog.
Add it and its handler tests with the first feature implementing this protocol.
Use the standard error envelope with details: []; no Retry-After value is promised.

## Verification and measurement plan

Implement real PostgreSQL concurrency tests alongside each corresponding service.
Use independent connections, explicit synchronization events/barriers, bounded
waits, and blocker inspection (e.g. pg_blocking_pids) to prove overlap. A sleep alone
is not proof. Exercise both meaningful orderings of each competing operation.

Verify committed state from a fresh Session, invariant preservation, rollback on
mid-transfer failure, bounded lock-timeout handling, and independent-Organization
progress. Stop and join workers before isolated cleanup; never clean while a worker
can still write. Use only the guarded product test target.

Measure lock-acquisition wait duration and recognized contention failures when
the protocol is implemented. Use bounded operation/route labels, not raw paths,
User IDs or Organization IDs. Current request duration logs do not separately
measure database lock wait time. Narrow the locks only after contention evidence
and a revised cross-row invariant protocol justify the change.

## References

- [PostgreSQL row locks](https://www.postgresql.org/docs/18/explicit-locking.html)
- [PostgreSQL lock timeout](https://www.postgresql.org/docs/18/runtime-config-client.html)
- [Access control](access-control.md), [Ticket lifecycle](ticket-lifecycle.md),
  and [API contract](api-contract.md).
