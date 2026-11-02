# Week 16 release and isolated recovery evidence

Recorded 2 November 2026. No live database restore, downgrade or data deletion
was performed. This rehearsal used synthetic records in `opsdesk_product_test`;
it is not evidence of a successful export/restore of the hosted demo itself.

## Release identity and schema

- Runtime source: `8a633d0c8c513a2ac5fa69afadd636981451db07`, normal merge of
  [PR #49](https://github.com/ozdemirr1/opsdesk/pull/49).
- Railway deployment: `3215ab49-07c6-4b91-9372-59c14d63f47e`, SUCCESS, `main`.
  It was created on 1 November and rechecked on 2 November.
- Source Alembic head, guarded test database and hosted `opsdesk_demo` all use
  `84c2f9a17d60`. Hosted revision was read through the existing guarded migration
  connection as `opsdesk_migrator`; no new grant on `alembic_version` was needed.
- Runtime `opsdesk_app` has SELECT/INSERT on `public.comments` and USAGE on its
  identity sequence. The narrow repair is documented in [development](development.md).
- Earlier deployed app used for compatibility: `b7800e4` (PR #48).
  Only its authenticated Ticket detail read was rehearsed against the expanded
  schema; this does not establish every old-version write path as compatible.

## Rehearsal sequence and results

1. Validate database name, role, server address and port exactly:
   `opsdesk_product_test`, `opsdesk_product_test_runner`, `127.0.0.1`, `5432`.
   Also require revision `84c2f9a17d60` and only the known product/probe tables.
2. Use the existing synthetic local acceptance fixtures: 2 Users, 2 Organizations,
   3 Memberships, 3 Tickets; add 1 synthetic Comment. Do not use customer data.
3. Snapshot all business rows, ordered by primary key, plus every sequence's
   `last_value` and `is_called`. Compare an in-memory SHA-256 of the serialized
   snapshots; password hashes and row payloads are not printed or committed.
4. Take a custom-format dump with PostgreSQL **18.6** `pg_dump`, check it with
   `pg_restore --list`, and keep it outside Git in a private temporary directory
   (directory mode 0700, file mode 0600). The first attempt safely stopped because
   the shell's default pg_dump was 14.19 while the server was 18.6; no restore ran
   from that failed dump. Explicit 18.6 tools completed the retry.
5. Recheck the exact target, close pooled connections, restore with
   `--clean --if-exists --no-owner --no-privileges --single-transaction --exit-on-error`.
   All row content and sequence values matched after restore, including the Comment.
6. Extract previous source `b7800e4` into a temporary directory, use its application
   and test helpers against the same guarded test database, and GET the synthetic
   customer's Ticket with its test token. Result: **200**, expected title, unchanged
   row/sequence digest afterward. No old version was deployed to Railway.
7. Clear only these test fixtures in dependency order, then run schema tests before
   ordinary data tests. Schema suite: **5 passed**; includes predecessor downgrade,
   re-upgrade, preserved Ticket data and recovery after an injected failure.
   `alembic check`: **No new upgrade operations detected**.
8. Ordinary PostgreSQL suite: **281 passed**. Final revision remained
   `84c2f9a17d60`; business tables were empty after test cleanup. No local dev or
   hosted data was used by these destructive checks.

Commands used after the preconditions above (PostgreSQL 18 tools must be on PATH):

```sh
pg_dump -h 127.0.0.1 -p 5432 -U opsdesk_product_test_runner \
  -d opsdesk_product_test -w --format=custom --file "$RECOVERY_DUMP"
pg_restore --list "$RECOVERY_DUMP"
pg_restore -h 127.0.0.1 -p 5432 -U opsdesk_product_test_runner \
  -d opsdesk_product_test -w --clean --if-exists --no-owner --no-privileges \
  --single-transaction --exit-on-error "$RECOVERY_DUMP"
# Empty the verified test fixtures before schema tests; use guarded environment
# settings from development.md. Run sequentially, never alongside another suite.
OPSDESK_RUN_SCHEMA_TESTS=1 .venv/bin/python -m pytest -q tests/schema
.venv/bin/alembic check
OPSDESK_RUN_INTEGRATION_TESTS=1 .venv/bin/python -m pytest -q tests/integration
```

`RECOVERY_DUMP` is a private temporary path supplied by the operator. Local TCP
trust was used for this rehearsal; no database password was stored in commands or
Git. These commands are destructive to the explicitly named **test** database and
must never be repointed to development or Railway. Stop if a precondition fails.

## Rollback and operational limits

An application rollback reselects a previous application revision; it does not undo
schema or data changes. Keeping the expanded schema enabled the bounded previous
app read above. Downgrading the comments migration drops Comment data: never use
that as an automatic response to a deployment error. Restore into an isolated
verified environment first; compare data and application behavior before planning
any separate live recovery.

The rehearsal's `--no-owner --no-privileges` intentionally does not restore hosted
roles or grants. Hosted backup scheduling, retention, external storage and a restore
from an actual hosted export still need verification. Before a future hosted
migration, obtain a restricted backup and rehearse it separately; today's local
exercise is not retroactive proof that such a backup preceded the earlier release.

At the last supplied usage screenshot (1 November), Railway showed $4.08 and
16 trial days remaining. This is historical, not a fresh balance or forecast.
Check project Usage before further deployment/traffic; do not enable a paid plan
implicitly. Before stopping a demo, secure/export and verify the data first;
removing a volume is not an acceptable cost-control shortcut.

2 November dependency review: full npm audit found **16 development-tool findings**
(14 moderate, 2 high); production-only audit found **0**. TLS verification stayed
enabled using the system CA file. Test/lint tooling is not a public application
server, but remains a build/developer risk: track a separate compatible dependency
update and run full checks, rather than force an audit fix during release closure.
No dependency remediation or Python security audit is claimed here.
Registration/login abuse limits and provider incident/audit review remain open.
Keep the preview limited to synthetic manual testing; broader invitation and an
unqualified production-ready claim remain blocked by these operational follow-ups.
