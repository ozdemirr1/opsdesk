# Ticket Creation Validation Contract

Reviewed: 15 September 2026. Design source: [issue #1](https://github.com/ozdemirr1/opsdesk/issues/1).

This document records the reviewed request policy for
`POST /organizations/{organization_id}/tickets`. It does not implement the endpoint,
apply a migration, or report passing application tests.

## Accepted Shape

The body must be a JSON object. Only required `title`, required `description`, and
optional `priority` are accepted. Both required fields must be strings; do not
coerce numbers, booleans, arrays, objects, or null into text.

Reject every other field with `422 validation_error`, including `ticket_id`,
`organization_id`, `requester_membership_id`, `creator_membership_id`,
`assignee_membership_id`, `status`, `created_at`, and `updated_at`. Aliases such as
`assignee` and unrelated unknown fields are also rejected, even if supplied values
match the server's intended values. Actor identities and the target organization
come from authenticated context and the authorized path, respectively.

## Text Rules

| Decision | title | description |
| --- | --- | --- |
| Required type | String, not null | String, not null |
| Minimum length after trimming | 1 | 1 |
| Maximum length after trimming | 255 | 10000 |
| Edge normalization | Python parameterless str.strip() | Python parameterless str.strip() |
| Forbidden before trimming | U+0000, tab U+0009, LF U+000A, CR U+000D | U+0000 |
| Internal formatting | Preserve remaining internal characters/spaces | Preserve internal characters, spaces, tabs, CR and LF |
| Length unit | Unicode code points | Unicode code points |

Validate the string type, reject the listed forbidden characters anywhere in the
original string, trim its edges, and then check length. Accepted text is stored in
its trimmed form. Never silently truncate overlong input. Python str.isspace()
defines the whitespace set used by parameterless str.strip(); ordinary space-only
trimming is not an equivalent implementation.

No case conversion or additional Unicode normalization is applied. Count using
Python len(string), not UTF-8 bytes or displayed glyphs. A visually combined character
may contain several code points. This policy does not claim to reject every invisible
character or to guarantee meaningful text. In particular, the title rule prohibits
the three named tab/line-control characters; it is not a general Unicode line-break
or control-character ban.

Description trimming may remove indentation at the very beginning or blank lines
at the end. Internal indentation remains unchanged; do not strip each line or dedent.
The NUL character U+0000 is distinct from the JSON null value. Both fail the relevant
rules, but for different reasons.

These are field-validation rules, not a precedence rule over authentication or
authorization errors. Shared error precedence remains in issue #3. Never return raw
input values or internal exceptions in validation errors.

## Priority

Accept exactly the strings `low`, `medium`, `high`, and `urgent`. Do not trim,
lowercase, or coerce this field. Omission alone selects `medium`. Explicit null,
empty strings, surrounding whitespace, unknown values, and non-string types produce
`422 validation_error`.

## Reviewed Request Examples

The examples below assume valid authentication, active User/membership/Organization,
and operation permission. Accepted validation produces `201 Created` only if the
future endpoint also commits successfully. Rejected requests create no Ticket.

### Trimmed text and omitted priority

```json
{
  "title": "  Login button is broken  ",
  "description": "  When I click, nothing happens.  "
}
```

Accepted. Stored title: `Login button is broken`; description:
`When I click, nothing happens.`; priority: `medium`.

### Internal indentation retained

```json
{
  "title": "Database connection timeout",
  "description": "  Traceback error:\n    Line 42: Connection refused\n  Please check.  ",
  "priority": "high"
}
```

Accepted. The exact normalized description is:

```json
"Traceback error:\n    Line 42: Connection refused\n  Please check."
```

### Minimum lengths

```json
{
  "title": "A",
  "description": "B"
}
```

Accepted. Both fields have one code point; omitted priority becomes medium.

### Forbidden title newline

```json
{
  "title": "Billing\nIssue",
  "description": "The invoice is wrong."
}
```

Rejected with `422 validation_error`. The same applies to a leading or trailing
LF, CR, or tab in title: trimming must not hide the prohibited input.

## Boundary and Rejection Matrix

`A × n` denotes a string containing exactly n copies of A, not literal request text.
Each row assumes all unrelated fields are valid. These are future test expectations,
not executable test results.

| Input variation | Expected validation result |
| --- | --- |
| title A × 255 / A × 256 | Accepted / 422 |
| Two spaces + title A × 255 + two spaces | Accepted; store exactly 255 As |
| description A × 10000 / A × 10001 | Accepted / 422 |
| Empty title or description | 422 |
| description containing only space, tab, and LF | 422 after trimming to empty |
| Missing title or description | 422 |
| Either required field is null, number, boolean, array, or object | 422; no coercion |
| NUL anywhere in either text field, including at an edge | 422 before trimming |
| Tab, CR, or LF anywhere in title | 422 before trimming |
| low / medium / high / urgent priority | Accepted exactly as supplied |
| Omitted priority | Accepted; medium |
| null / empty / unknown / non-string priority | 422 |
| Priority with surrounding whitespace or uppercase letters | 422; no normalization |
| status=open or assignee_membership_id=null supplied by client | 422 despite matching creation defaults |
| Any other unlisted request field | 422 |

## Persistence Handoff

Issue #8 must apply the agreed limits to persisted text: title length 1..255 and
description length 1..10000, with required columns. Preserve text types; length limits
do not require changing the columns to varchar. These are planned schema constraints,
not an applied migration. No SQL CHECK should silently normalize or truncate input.

Application normalization is authoritative for this request. A PostgreSQL POSIX
whitespace expression must not be assumed identical to Python's whitespace set;
review shared edge cases before choosing any extra database nonblank check. Such
a check must not reject text accepted under this contract. PostgreSQL itself cannot
store U+0000 in text, which is why request validation rejects it before persistence.

## References

- [Python text sequences and str.strip](https://docs.python.org/3/library/stdtypes.html#str.strip)
- [PostgreSQL character types](https://www.postgresql.org/docs/18/datatype-character.html)
- [API baseline](api-contract.md)
- [Relational model](relational-model.md)
