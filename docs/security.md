# Security

This file documents the authentication/authorization architecture and the security/data-
protection controls added by the Administration module. It doesn't duplicate `docs/api.md`'s
per-endpoint auth column — see that file for exactly which role can call which endpoint.

## Authentication
`POST /auth/login` (OAuth2 password flow, form-urlencoded) issues a JWT (`core/security.py`,
PyJWT, `HS256`, `access_token_expire_minutes` from config). Passwords are hashed with `pwdlib`'s
`PasswordHash.recommended()` — never stored or logged in plain text, and no schema anywhere in
the codebase (`UserRead`, `CurrentUser`, etc.) includes `hashed_password`; it is not reachable
through any API response.

**Inactive accounts are rejected at both entry points, not just one.** `deps.py`'s
`get_current_user` (checked on every authenticated request) and `routers/auth.py`'s `login`
(checked before token issuance) both reject a user whose `is_active` is `false`. This closes a
real gap that existed before the Administration module: previously, deactivating a user only
blocked their *next login* — an already-issued JWT kept working until it naturally expired. Now
a deactivation takes effect on the very next request the deactivated user's existing token makes.

## Authorization
There is exactly **one** authorization primitive in this codebase: `deps.py`'s
`require_role(*role_names)`, which checks `current_user.role.name` and raises 403 otherwise.
There is no permissions table, no decorator-based system, and no middleware-based authorization
anywhere else — confirmed by grepping every reference to `current_user.role` in the codebase.
Every router applies `Depends(require_role(...))` to its write (and, for Administration, read)
endpoints; there is nothing else to bypass, and nothing else to keep in sync.

**All authorization is enforced server-side.** No endpoint relies on the frontend to hide a
button or route as its security boundary — the frontend's `AdminGuard` component (client-side)
exists purely to show a clear "Access restricted" message to a non-Administrator instead of a
page full of failed requests; every request it would have made is independently rejected by the
backend regardless of whether that component ran at all.

### Default roles
Seeded by `backend/app/db/seed.py`, unchanged by the Administration module (confirmed with the
user during planning — the brief's own 6-role list was shorthand for the existing 7, not a rename
instruction):

| Role | Typical scope |
|---|---|
| Administrator | Full access, including the Administration module itself |
| Management | Cost & Revenue, Alerts, Reports — management/analyst decision-support |
| Production Engineer | Wells, Production, Production Loss |
| Maintenance Engineer | Equipment, Maintenance |
| Production Operator | Operational read/write on Production-adjacent data |
| Analyst | Broad read access, operational actions (alerts, insights, what-if, reports) |
| Viewer | Read-only everywhere, excluded from every "any except Viewer" write action |

### Default permissions
The full, authoritative module/action → role matrix is served live at `GET
/administration/permissions` (`services/permissions.py`) and rendered at
`/administration/roles` in the UI — it is generated from the same `require_role(...)` calls that
actually enforce access, so it can never silently drift from reality. It is deliberately a
**read-only view**, not an editable permission-granting system: introducing one would mean
rewriting authorization across every router to consult it, and would risk the exact
permissions-table-vs-enforcement drift this design avoids by construction. Two related, equally
deliberate scope limits:

- **Role management is read-only** — no create/delete-role endpoint or UI. A role name is a
  hard-coded string literal inside `require_role(...)` calls; a role created through a UI would
  have zero actual enforcement anywhere until a developer edited code, so presenting role
  creation as functional would be dishonest. **User → role assignment** (`PUT /users/{id}`) is
  fully real, since `role_id` is a genuine foreign key.
- Where the brief's requested module/action grid implies a permission that isn't actually
  enforced (e.g. there is no Wells delete endpoint at all), the matrix records that gap via a
  `note` field rather than inventing an endpoint or a permission that doesn't exist.

## Administration module security controls
- Every `/administration/*` endpoint, and the new `POST`/`PUT`/`GET /users/{id}` endpoints,
  require the `Administrator` role — verified by automated tests asserting a 403 for each of the
  other 6 roles against every endpoint (`backend/tests/test_administration_router.py`,
  `test_users_router.py`).
- `UserRead` never includes `hashed_password`; `UserCreate`/`UserUpdate` never accept a password
  change through the profile-management endpoints (`PUT /users/{id}` has no `password` field at
  all) — password changes live exclusively in `routers/auth.py`, see "Password management & email
  verification" below.
- `GET /administration/ai-config` and `/system-health` only ever read the already-safe
  `provider_name`/`model`/`is_configured` properties of the resolved `AIProvider` instance
  (`services/ai_providers/factory.py`) — the raw key fields on `Settings`
  (`openai_api_key`/`anthropic_api_key`/`google_api_key`/`local_ai_base_url`) and other secrets
  (`secret_key`, `database_url`) are never read by any Administration code path. There is
  therefore no key-shaped value for a bug to accidentally leak into a response, log line, or
  error message — this is a property of what the code touches, not a redaction step applied
  after the fact.
- `GET /administration/system-health` reports status strings only (`"connected"`, `"running"`,
  etc.), the app version, and `environment` — never a connection string, port, hostname, or other
  infrastructure detail.

## Audit logging
`services/audit.py::record_audit_event()` is the one write path for `AuditLog`
(`models/reporting.py`), wired into: user create/update/role-change/activate/deactivate, `PUT
/settings/{key}`, `POST /reports`, `POST /what-if/scenarios`, and `POST /ai-insights/run` — the
exact set the brief names, not every CRUD endpoint in every router (bounding regression risk on
an otherwise-stable codebase).

Every row records: an event id, the acting user (nullable — a `None` user is recorded as
"System"), the action, the resource type, the resource id, a timestamp, a `status` (`"success"`
by default), and an optional structured `metadata_json` blob for non-secret extra context (e.g.
`{"from_role": "Analyst", "to_role": "Management"}` for a role change). **Passwords, API keys,
and other secrets are never passed into `details`/`metadata` by any call site** — verified by a
test that creates a user with a real password and asserts the password string never appears
anywhere in the audit log API response.

Logging is wrapped in `try`/`except`: a failure to write an audit row is caught and logged to the
application logger, never raised — so an audit-logging failure can never break the action it was
describing. The audit log itself is **read-only** through the API — there is no update or delete
endpoint, by design, since a mutable audit trail isn't one.

## Data protection
- No endpoint anywhere in the codebase returns `hashed_password`, `secret_key`, `database_url`,
  or any of the 4 AI provider key/URL settings — confirmed by grep across every schema class, not
  just Administration's.
- Error responses use FastAPI's standard `HTTPException(detail=...)` with short, generic messages
  (`"User not found"`, `"A user with this email already exists"`) — never a stack trace, SQL
  fragment, or raw exception string reaches the client.
- Frontend source contains no API keys or secrets — `NEXT_PUBLIC_*` environment variables are the
  only ones ever bundled into client code, and none of the AI/database/JWT secrets use that
  prefix.

## Password management & email verification
Self-service password change, forgot-password, reset-password, and email verification —
`routers/auth.py`: `POST /auth/change-password` (authenticated), `POST /auth/forgot-password`
and `POST /auth/reset-password` (public), `POST /auth/send-verification` (authenticated,
rate-limited) and `POST /auth/verify-email` (public).

**Stateless tokens, no token-storage table.** Reset/verify tokens are JWTs with a `purpose`
claim (`core/security.py`'s `create_purpose_token`/`decode_purpose_token`) — the same signing
machinery as login tokens, but never accepted by `get_current_user` (no `purpose` claim there)
and vice versa.

**Reset tokens are single-use via a password-hash fingerprint, not a database row.**
`password_fingerprint(hashed_password)` is an HMAC-SHA256 of the hash, keyed on `secret_key`. A
reset token embeds the fingerprint of the hash *at issue time*; `reset-password` rejects the
token if the current DB fingerprint no longer matches — so consuming the token once (which
changes the hash) automatically invalidates it, and an intervening password change (however it
happened) invalidates any outstanding token too. Rotating `secret_key` invalidates every
outstanding reset/verification token as a free side effect. `reset-password` also re-checks
`is_active` at consume time, not just at issue time in `forgot-password`, since an account can be
deactivated in the window between the two. Every failure mode — expired, garbage, wrong purpose,
fingerprint mismatch, inactive account — returns the identical generic "Invalid or expired reset
link." message, so no response signals which case occurred.

**Forgot-password never reveals whether an email exists.** `POST /auth/forgot-password` always
returns the same generic message regardless of whether the account exists or is active; a token is
only generated and an "email" only "sent" for a real, active account. Rate-limited (3 requests /
15 minutes, keyed by the submitted email — `services/rate_limit.py::check_email_rate_limit`) to
slow repeated probing of one address; with no IP plumbing anywhere in this codebase, it cannot
stop an attacker who rotates target addresses — an accepted limitation, not a gap that was missed.

**Dev-mode-only mail delivery, explicit about it.** `services/mail_providers/` mirrors the AI
provider abstraction (`services/ai_providers/`) — only `ConsoleMailProvider` exists today, which
logs the email instead of sending it. The `mail_provider="console"` config comment states
explicitly that this **must never be selected in a real deployment**, since it writes reset/
verification tokens into application logs. The API response additionally echoes the token/link
(`debug_token`/`debug_reset_url`/`debug_verify_url`) but **only when `ENVIRONMENT=development`**
— an allowlist on the exact value (fails closed on typos or a new deploy tier), not a blocklist on
`"production"`. Response-gating is a convenience on top of the real control (never select
`mail_provider="console"` in production), not a substitute for it.

**A known, accepted limitation: access tokens outlive a password reset/change.** `get_current_user`
checks `is_active` but not the password hash, so an access token issued before a password
change/reset stays valid for up to `access_token_expire_minutes` (60 min default) afterward — the
exact scenario reset-password exists to protect against. Closing this fully would mean embedding
the same fingerprint check into every authenticated request in `deps.py` (this codebase's
highest-blast-radius file) and would ripple into every test that builds a token directly (e.g.
`conftest.py`'s `auth_headers` fixture, used by ~450 backend tests). Deliberately scoped out of
this feature rather than silently shipped as if the gap didn't exist — if this matters for a real
deployment, revisit `deps.py` directly rather than working around it elsewhere.

**Login is not gated on `is_email_verified`.** There is no self-registration in this app — only
Administrator-driven `POST /users` creates accounts — so verification is a foundation/
informational feature, not an access gate; a real email that never arrives (this is dev-mode!)
can never lock anyone out. Existing (already-trusted, admin-created) accounts are backfilled to
verified by the adding migration; new accounts default unverified until `verify-email` is called.

## Testing
`backend/tests/test_administration_router.py`, `test_users_router.py`, and `test_audit.py` cover:
authorized (Administrator) access to every Administration endpoint; a 403 for each of the other 6
roles against every Administration endpoint and the admin-only `/users` endpoints; password never
present in a create/update response; a deactivated user's already-issued token being rejected on
its next request (proving the `is_active` fix); settings validation (numeric, allowed-value, and
free-text branches all rejecting invalid input); an AI key set in test environment variables never
appearing in the `/administration/ai-config` response; and audit rows being written with no
secret content for every hooked endpoint. The full existing suite (373 tests across the other 10
modules) was re-run after every change in this module and shows zero regressions.
