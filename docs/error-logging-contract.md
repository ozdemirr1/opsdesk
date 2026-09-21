# Shared API Errors and Request Logging Contract

Reviewed with Furkan on 18 September 2026. This resolves the #3 subset required
by #10; other #3 validation, response, ordering, no-op, and precedence decisions
remain open. This document is a contract, not implementation evidence.

## Public errors

Retain `{"error": {"code": "...", "message": "...", "details": []}}`.
All errors include details; non-field errors use an empty array. Public codes and
messages come from server-controlled definitions, not exception text. Existing
business HTTP/code mappings in api-contract.md remain authoritative. Input schema
failures use 422; business state conflicts use 409 and authorization failures 403.
An infrastructure failure does not establish that the request was otherwise valid.

Known field paths include `body.email`, `query.limit`, and `path.organization_id`.
Only server-known schema names may be reflected. Unknown client field names are
not echoed; use the safe source-level location instead. Do not serialize Pydantic
input/ctx, raw rejected values, passwords, hashes, tokens, SQL, or exception text.

- Malformed JSON: 400 invalid_json, distinct from 422 validation_error for a
  successfully parsed body that fails its input schema.
- JSON-body endpoints accept application/json including a charset parameter.
  A present body with missing or unsupported Content-Type returns
  415 unsupported_media_type. This is explicit behavior, not a framework assumption.
- Unexpected errors, including unmapped database failures: 500 internal_error,
  message `An unexpected error occurred.`, details []. Only a specifically known
  persistence constraint may be translated into its approved business conflict.
- Unmatched route: 404 not_found. Unsupported HTTP method: 405 method_not_allowed.
  Preserve necessary protocol headers such as Allow.
- Bearer authentication 401 responses retain WWW-Authenticate: Bearer.

## Request identity and diagnostics

Generate a new server UUID for every request. Ignore incoming X-Request-ID values;
return the server value in X-Request-ID and use it in the application request log.
No distributed tracing or client correlation-ID propagation is introduced.

Log bounded metadata: server request ID, HTTP method, matched route template,
status code, and elapsed duration. Use a fixed unmatched-route label when there
is no matched template. Do not log raw URLs, paths, queries, bodies, Authorization
headers, arbitrary inbound headers, credentials, raw exception messages or tokens.
Metadata must be bounded/server-controlled even when the request is hostile.

These choices reduce disclosure and injection risk; they do not automatically
secure Uvicorn, proxies, custom loggers, debug output, or exception serialization.
Request middleware cannot protect earlier startup errors. Preserve and verify
existing safe startup-validation reporting separately. Runtime access-log behavior
must be reviewed before claiming raw paths are absent from the development logs.

## Acceptance examples

- Broken JSON syntax -> 400 invalid_json; valid JSON missing a required field ->
  422 validation_error, without echoing supplied values.
- Otherwise valid JSON body with text/plain -> 415 unsupported_media_type.
- Unknown backend error -> generic 500, not email_already_exists or unauthenticated.
- Hostile incoming request ID -> ignored; response/log share a new server UUID.
- A request to /organizations/42 is logged using /organizations/{organization_id}
  when that route exists; arbitrary unmatched paths are replaced by a fixed label.
- A known conflict returns its existing approved HTTP/code and empty details.

Use bounded test-only routes for implementation tests; no product feature endpoint
is added just to exercise this infrastructure. Test headers, error envelopes,
synthetic-secret exclusion, and request/log correlation as externally visible
behavior. Full overlapping business-failure precedence remains #3 work before
those feature endpoints are implemented.


## Implementation Clarifications and Evidence — 21 September 2026

- The response contains at most 20 validation details. Missing fields use
  Field is required.; extras use Unexpected field.; other validation failures use
  Invalid value. Only known top-level fields are exposed, with deeper paths reduced
  to their known ancestor and unknown fields to body/query/path (or request).
- A present body requires one Content-Type header with application/json as the
  media type, case-insensitively; parameters are permitted. Empty required bodies
  produce 422. The Content-Type gate precedes JSON parsing and schema validation.
  This transport order does not settle overlapping business authorization failures.
- Unmapped framework 4xx errors retain their HTTP status with http_error and the
  fixed message Request could not be processed. Arbitrary exception detail/headers
  are not copied; the current supported headers are Allow and bearer challenges.
- HTTP diagnostics bound route templates to 200 characters, replace unknown methods
  with OTHER, and record response_started/unexpected_error flags. After response
  start, a new 500 body cannot be sent; raise a fixed error and preserve the sent status
  in diagnostics. Before response start, unexpected errors receive generic 500.
- Configure Uvicorn with --no-access-log. Local real-server evidence verified a safe
  unmatched-route response/log with matching server ID and absent synthetic secrets.
  TestClient tests cover handled, validation, framework, and unexpected failures.
- Local checks: 101 non-integration tests passed, 62 database/schema cases deselected,
  Ruff passes and 41 Python files formatted. These are local results; hosted CI and
  PR merge must be verified separately. Remaining #3/#4 decisions stay open.
