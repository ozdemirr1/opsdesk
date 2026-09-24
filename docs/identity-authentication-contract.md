# Identity and Authentication Contract

Reviewed: 15 September 2026. Design source: [issue #2](https://github.com/ozdemirr1/opsdesk/issues/2).

This is the request, storage, and token contract for registration, login, current-user
resolution, and shared email lookup. The registration slice was implemented locally on
24 September 2026; login, JWT validation, current-user resolution, and organization
authorization remain design contracts. The same email identity policy applies when an
administrator adds an existing User.

## Request and Response Boundaries

- POST /users and POST /auth/login accept a JSON object containing exactly required
  string fields email and password. Reject missing, null, wrong-type, or extra fields
  with 422 validation_error. No automatic conversion of values to strings.
- Registration returns 201 only after commit, with UserProfile: user_id, email,
  is_active. Registration creates an active global User, not a membership or role.
- Login returns 200 with exactly access_token and token_type="bearer".
- GET /users/me returns 200 UserProfile after current-user authentication.
- Passwords, hashes, secrets, complete tokens, raw request bodies, SQL, and traces
  must not enter errors or logs. The successful login token is an intentional
  response field. Successful registration and current-user responses exclude hashes.

## Email Identity

1. Require a string, then trim its leading/trailing whitespace using Python str.strip().
2. Require the trimmed address to be ASCII and at most 254 characters (also 254 bytes).
3. Validate a bare address with the maintained email-validator library. Disable DNS
   deliverability checks; reject display names, quoted local parts, domain literals,
   empty local parts, and SMTPUTF8 local parts. Use its ordinary public-domain syntax
   rules, including a dotted domain; do not accept localhost as a production identity.
4. Use the validated ASCII address representation and lowercase it for storage/lookup.
   If the library's display-normalized domain is Unicode, use its ASCII representation.
   ASCII punycode domain labels remain subject to library validation; raw non-ASCII
   email input is outside this release's accepted input contract.
5. Preserve dots and plus-tags. Do not remove internal spaces to repair an address.

No separate arbitrary minimum length replaces syntax validation. Both the trimmed
input and canonical stored value must satisfy the 254-character limit. Registration,
login, and member addition use the same canonicalization function. Addresses differing
only in case identify the same OpsDesk account by product policy, not by a claim that
every mail provider treats local parts identically.

| Input | Canonical identity / outcome |
| --- | --- |
| `  Furkan@example.com  ` | furkan@example.com |
| `furkan@EXAMPLE.COM` | furkan@example.com; same identity |
| `furkan+support@example.com` | Separate canonical identity; preserve +support |
| `fur.kan@example.com` | Separate canonical identity; preserve dot |
| `fur kan@example.com` | 422; internal space |
| `fürkan@example.com` | 422; non-ASCII input |
| `Furkan <furkan@example.com>` | 422; display name |
| `furkan@` | 422; malformed address |
| null, number, boolean, array, object, or missing field | 422 |
| Trimmed ASCII input of length 255 | 422 |

Valid syntax establishes neither mailbox existence nor ownership. Email verification
and email delivery remain outside Month 03. Distinct canonical identities do not
prove distinct people or even that either account has already been registered.

## Email Persistence and Duplicate Registration

Store the canonical lowercase ASCII value only; User IDs remain immutable relationship
keys. A named UNIQUE constraint on canonical email closes concurrent duplicate races.
UNIQUE itself does not normalize values. The Users schema must also reject noncanonical
stored case, non-ASCII text, whitespace in canonical addresses, and lengths outside
1..254. ASCII lowercase checking must have deterministic semantics, independent of a
locale-specific case conversion. Full email syntax remains an application check.

An already registered canonical email returns 409 email_already_exists, regardless
of active state, without disclosing account state. Concurrent attempts create exactly
one User; the conflicting attempt receives that controlled error. Translate only the
known email-uniqueness violation; unrelated persistence errors are not duplicate-email
errors. Failed registration leaves no new User committed.

## Password Input and Storage

Require a string that can be encoded as UTF-8; reject malformed Unicode, including
unpaired surrogate values, with 422. Apply Unicode NFC, then measure length in Unicode
code points. Minimum: 15; maximum: 128. Never silently truncate, trim, or change case.
Preserve leading, trailing, and internal whitespace. Do not require a mixture of
uppercase letters, digits, or symbols. Unicode NFC canonical equivalence does not
mean all visually similar text becomes equivalent.

The same normalization and length/type checks apply to registration and login.
There is no Ticket-specific tab, newline, or NUL ban on passwords in this contract;
they are passed as normalized Unicode to the maintained hashing/verification library,
not stored as plaintext PostgreSQL text. Implementation must test accepted character
handling rather than silently drop or terminate input at a control character.

| Input condition | Outcome |
| --- | --- |
| 14 code points after NFC | 422 |
| 15 or 128 code points after NFC | Accepted structurally |
| 129 code points after NFC | 422 |
| Missing, null, or non-string | 422 |
| Surrounding/internal spaces | Preserved and counted |
| Case difference | Preserved; changes the password |
| Canonically equivalent composed/decomposed text | Same NFC input to verification |

Registration hashes the normalized password with Argon2id through a maintained
library. The library manages salts, encoded parameters, and verification. Persist
only the encoded hash. Login verifies the normalized submitted password against the
stored encoding; never generate a new salted hash and compare the encodings directly.
Concrete library versions and work-factor performance are verified during implementation.

This policy specifies structural acceptance, not proof of password strength or full
NIST compliance. Release exposure controls, including password-guessing resistance,
remain part of the preview security review; no compromised-password service is
implicitly integrated by this design task.

## Login Failures

For otherwise valid requests, unknown email, incorrect password, and inactive User
all return the same 401 unauthenticated response without a token. Do not disclose
which condition failed. Use a library-created dummy hash verification for unknown
Users, and avoid an early inactive-account branch that skips comparable verification
work. This reduces timing differences; it does not guarantee identical response times.

Malformed fields still receive 422. A database outage or unexpected hashing failure
is an infrastructure failure, not evidence of invalid credentials; safe server-error
mapping and overlapping error precedence are handled in issue #3/#10.

## JWT Issuance and Validation

Use a maintained JWT library. The server permits HS256 only; never derive the allowed
algorithm from an untrusted header. A header requesting another algorithm, including
none, is rejected. Verify the signature before using claims as trusted identity.

The signing secret comes from environment-backed configuration, has no fallback,
and is generated with at least 32 cryptographically random bytes of entropy. A
minimum-length configuration check cannot prove entropy. Do not generate or commit
a real secret during design. Authentication composition requires valid signing
configuration; the independent foundation application does not require it yet.

| Claim | Required contract |
| --- | --- |
| sub | Canonical ASCII decimal string for a positive User bigint ID; no sign or leading zero; within signed bigint range |
| iat | Nonnegative integer Unix seconds; no float, boolean, or numeric-string coercion; must not be in the future |
| exp | Integer Unix seconds with the same strict type rule; exactly iat + 1800 |
| iss | String exactly opsdesk |
| aud | String exactly opsdesk-api; arrays are not accepted in this profile |

Issue these five claims only; no roles, membership, email, or organization permissions.
They are all mandatory when validating. Additional incoming claims never grant
authorization; any extra registered claim accepted by the library, such as nbf,
must retain its validation rather than bypass it. Expiration rejects now >= exp;
future issuance rejects iat > now. Leeway is zero seconds. Use an injected UTC clock
for testable issuance; successful verification must enforce types and cross-field
relationships beyond presence checks. JWTs are signed, not encrypted.

## Current User and Organization Authorization

After signature and claim validation, load the current User from persistence on every
protected request. Missing or inactive Users are rejected. Missing, invalid, or expired
bearer credentials and missing/inactive Users share 401 unauthenticated with
WWW-Authenticate: Bearer. Dependency/database failures must not be disguised as 401.

Current active identity does not authorize tenant operations. Check current membership,
Organization state, resource visibility, and operation permissions separately under
the existing access-control and lifecycle contracts. JWT role-like data is never a
substitute for these checks. Refresh tokens, MFA, password reset, and per-token
revocation workflows remain out of scope.

## Reviewed Examples and Future Verification

Synthetic registration request; the example password is test material, not a secret
to use in a real account:

```json
{
  "email": "  Furkan@example.com  ",
  "password": "river valley lantern"
}
```

For a new canonical identity and successful commit: 201 UserProfile with
email=furkan@example.com. Repeating the canonical identity: 409 email_already_exists.
Login with the valid fields but unknown User/wrong password/inactive User: generic 401.
Appending an unknown role or is_active field: 422; no new User persisted.

Synthetic decoded payload; this is neither a signed token nor a credential:

```json
{
  "sub": "42",
  "iat": 1800000000,
  "exp": 1800001800,
  "iss": "opsdesk",
  "aud": "opsdesk-api"
}
```

With a valid signature, at time 1800000300 the token's time checks pass. At time
1800001800 it is expired. A future iat, missing claim, numeric sub, string/boolean
timestamp, wrong issuer/audience, array audience, invalid signature, wrong algorithm,
or malformed token produces protected-request 401. Valid claims with missing or
inactive User also produce 401. Protected-token failures are not login-body tests.

Registration implementation covers exact email length and syntax boundaries, wrong
types, forbidden fields, NFC length-changing examples, password space/case preservation,
Argon2id verification, safe response projection, explicit rollback, named-constraint
mapping, and fresh-session PostgreSQL persistence. Local verification on 24 September
2026 passed 147 non-integration tests and all 66 PostgreSQL integration tests.

The independent-session overlapping duplicate race remains required before issue #11
is complete. Dummy-hash login behavior, the complete token rejection matrix, and
protected-current-user behavior belong to the later login/authentication slices and are
still planned tests. Hosted CI and pull-request review also remain separate from this
local evidence.

## References

- [API contract](api-contract.md)
- [Access-control matrix](access-control.md)
- [Email-validator documentation](https://github.com/JoshData/python-email-validator)
- [SMTP local-part case sensitivity](https://www.rfc-editor.org/rfc/rfc5321#section-2.4)
- [NIST password guidance](https://pages.nist.gov/800-63-4/sp800-63b.html#passwordver)
- [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [PyJWT validation options](https://pyjwt.readthedocs.io/en/stable/api.html)
