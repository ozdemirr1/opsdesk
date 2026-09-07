# OpsDesk

OpsDesk is a multi-tenant support ticket management API designed for B2B
environments. Each organization has its own membership and data-access boundary.

## Problem

Support requests tracked through scattered messages are difficult to follow.
Customers lack visibility into progress, while support teams struggle to track
responsibility, conversations, and resolution status. OpsDesk aims to solve this
by providing a centralized system where each organization's data remains isolated
and actions follow explicit permission rules.

## Target Users

- **Customer:** Submits support requests and follows permitted tickets.
- **Agent:** Handles permitted tickets and communicates with customers.
- **Admin:** Manages support operations and permitted membership actions within
  an organization.
- **Owner:** Holds organization ownership and manages ownership-level actions.

## Planned Capabilities

The API is currently being designed to support the following core workflows:

- Global user identities linked to organization-specific memberships and roles.
- Organization data isolation enforced by the backend.
- Ticket lifecycle rules for `open`, `in_progress`, `resolved`, and `closed`.
- Ticket assignment and role-based access control (RBAC), combined with
  organization and ticket-level permission checks.
- Permission-controlled ticket comments and attachment metadata tracking.

## Project Status

The project is in the requirements and domain-design phase. Implementation has
not started. File-content upload and storage are outside the current scope.

See [Product requirements](docs/requirements.md) for the initial scope,
acceptance scenarios, and unresolved design decisions.
