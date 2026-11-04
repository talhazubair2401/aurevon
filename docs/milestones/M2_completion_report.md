# AureVon M2 Completion Report: Data and Identity

**Date:** 4 November 2026
**Baseline:** MTS v2.1, decision record 0003 (P-05 and D-12, approved with three clarifications)
**Commit:** `0eb84e7` on `main`
**CI:** all four jobs passed on the first run
**Status:** M2 is complete. This report is awaiting your approval before M3 starts.

## 1. What was built

### Identity (MTS v2.1 A-22)

**Accounts**
- **One account model.** Each account is a customer or staff account. That type is fixed for good: a database trigger refuses any change to it.
- **Same email, two accounts.** One email address can hold a customer account and a separate staff account.
- **No superuser.** There is no `is_superuser` or `is_staff` flag, and nothing checks for one.

**Each realm gets its own:**
- session table
- cookie:
  - customer: `__Host-av_session`, `SameSite=Lax`
  - staff: `__Secure-av_staff`, limited to `/api/v1/staff/`, `SameSite=Strict`
- CSRF token
- sign-in endpoint

**How a session works**
- The cookie carries a random token. The database stores only a hash of it.
- Every request re-reads the session row, so revoking a session takes effect on the very next request.

### Staff roles and permissions (decision 1)

- **Roles:** six fixed roles. Each staff account holds exactly one.
- **The matrix lives in code.** It is defined in `permissions.py`, written to the database on every migration, and pinned by tests one cell at a time.
- **Default deny.** Every staff endpoint must declare the permission it needs. A test walks the URL configuration to prove that none is missing.
- **Store Admin limits:**
  - cannot suspend or end the sessions of an Owner or Store Admin
  - only an Owner reactivates an account
  - store settings only, never security settings
  - aggregate reports only

### Staff sign-in and sessions (decisions 2 and 3)

**Signing in**
- Password first, then a code from an authenticator app (TOTP).
- Authenticator secrets are encrypted at rest.
- A code can't be used twice, and one 30-second step of clock drift is allowed.
- Codes match the RFC 6238 test vectors.

**Recovery codes**
- 10 single-use codes, stored hashed and shown once.
- Signing in with a recovery code forces the person to set up a new authenticator before they can do anything else.

**Sessions**
- Signed out after 30 minutes of inactivity, with a 12-hour hard limit.
- Staff can see and end their own sessions.
- Password changes and new authenticators end every other session.

**Lockout**
- 5 failures in 15 minutes (password or code) lock sign-in for 15 minutes.
- The lock also ends the account's sessions and emails every Owner.
- There is a per-address limit as well.
- Unknown and known emails get identical responses.

**Fresh confirmation**
- These actions need a new authenticator code, valid for 5 minutes: invites, role changes, suspension, reactivation, deactivation, recovery approval, security settings, password and authenticator changes.
- Ending another person's sessions deliberately needs no fresh code, so a compromised account can be cut off instantly.

**Invites and password reset**
- Invite links last 48 hours.
- Password reset needs the 30-minute email link **and** an authenticator code. Email alone is never enough.

### Recovery and Owner protection (decision 4, clarifications 1 and 3)

**Assisted recovery**
- Approved by an Owner. Nobody can approve their own recovery.
- For staff it proceeds at once: the old credentials stop working and a 30-minute recovery link is emailed.

**Owner recovery**
- Waits 24 hours.
- During the wait, every registered recovery channel gets a notice with an immediate cancellation link. Today the channels are the sign-in email plus an optional recovery email.
- The cancellation link works without signing in. Any Owner, or the affected Owner, can also cancel from the dashboard.
- The old credentials keep working during the wait, so a real Owner who still has access can simply cancel.
- When the wait ends, a scheduled job (every minute) invalidates the old credentials and sends the link.

**Break-glass**
- `breakglass_recover_owner` needs both server access and the sealed single-use code from `create_breakglass_code`.
- It alerts every Owner.
- Failed attempts are always audited.

**One-Owner start**
- Setup can begin with one Owner (`create_owner`).
- Every staff page then shows a persistent warning.
- `security_status` fails until there are two active Owners and a sealed break-glass code. It is part of the launch checklist.

**Last Owner**
- The last active Owner can't be suspended, deactivated or demoted.

### Customers (decisions 3.2, 3.3a, 3.4)

**API**
- Register, verify email, sign in, sign out, current session.
- Password reset, which signs the customer out everywhere.
- List sessions, revoke one, revoke all others (clarification 2).

**Sessions**
- **Without "remember me":** the session ends when the browser closes, with a 24-hour cap on the server.
- **With "remember me":** 30 days, extended with each visit, never beyond 90 days.

**Failures**
- After 5 failures, growing delays: 30 s, 60 s, 120 s and so on, up to 15 minutes.
- There is no hard lockout.
- Registration and reset requests never reveal whether an email is registered.

### Governance

**Audit log**
- Append-only: a database trigger refuses updates and deletes.
- Records the actor, before and after values, IP address and request ID.

**Email**
- Emails are queued only after the database change commits, so a rolled-back change never sends anything.

**Store settings**
- The refund dual-approval threshold exists now as a store setting.
- Until you set an amount at M8, every refund needs a second approver.

### Staff dashboard (`/staff/`)

**Screens**
- Sign-in, including the recovery-code route.
- Invite enrolment, with a QR code rendered by our own server.
- Recovery.
- Forgot and reset password.
- Recovery cancellation.
- Overview, with the security warnings.
- **My account:** sessions, password, recovery email, new authenticator, recovery codes.
- **Team:** invite, role, suspend, end sessions, reactivate, deactivate, recovery.
- **Audit log:** filter, pages of older entries.
- **Settings.**

**Behaviour**
- A fresh-confirmation dialog appears automatically when an action needs it.
- Link tokens travel in the URL fragment and are removed from the address bar, so they never reach servers or logs.

### Operations

- **Runbook:** `docs/runbooks/staff-accounts.md`.
- **Mailpit:** emails go to Mailpit in the local stack.
- **Production settings** now require `MFA_ENCRYPTION_KEY`.

## 2. Tests

| Check | Result |
| --- | --- |
| Backend pytest (PostgreSQL) | **104 passed** (81 new) |
| End-to-end, Playwright through the proxy and Mailpit | **19 passed** (4 new) |
| ruff, mypy (strict), import boundaries (3 contracts), migrations check, deploy check, bandit, pip-audit | Pass |
| Prettier, ESLint, TypeScript, Vitest (10), both production builds, pnpm audit | Pass |
| API contract (schema and typed client in sync) | Pass |
| Scheduler running; worker answers ping | Pass |

**What the new backend tests prove:**
- **Realm separation:**
  - A customer session gets `401` on every protected staff route, with the routes listed from the URL configuration.
  - Staff sessions are ignored on customer endpoints, and neither realm can sign in through the other's endpoint.
  - The account type can't change.
  - Cookie attributes are correct.
  - The superuser flag grants nothing.
- **Sign-in and codes:**
  - RFC 6238 test vectors, replay refusal, lockout and Owner alerts.
  - CSRF, idle and absolute session limits, and fresh confirmation with its 5-minute expiry.
  - Recovery-code re-enrolment.
- **Roles:** every cell of the matrix that decision 0003 refines.
- **Administration and recovery:**
  - Suspension ends sessions on the next request, and Store Admin limits hold.
  - Last-Owner guard.
  - The 24-hour wait, cancellation, release and break-glass.
  - `security_status`.
- **Customers:** session lengths, rolling cookie, session revocation, growing delays.
- **Governance:**
  - The audit log is append-only.
  - Settings permissions.
  - Email is sent only after commit.

**What the end-to-end staff journey covers:**
1. The real `create_owner` command, and a real email in Mailpit.
2. Enrolment with a computed TOTP code.
3. The single-Owner warning.
4. An invite, and the new member enrolling.
5. The Owner suspends the member, and the member's open page loses its session at once.
6. The audit-log entry.
7. A customer session is refused by the staff API.

**Defect caught by a test:** a failed break-glass attempt's audit entry was rolled back along with the refused transaction. It is now recorded outside that transaction.

## 3. Choices made in implementation (not new architecture)

1. **"Core schema" scope.** I built the identity, roles, sessions, audit and settings tables. Catalogue, inventory, order and payment tables arrive with M5, M7, M8 and M9 as MTS §16 lists them, so they are designed alongside their rules.
2. **Sessions are read from PostgreSQL on every request, not cached in Redis.** The MTS proposed caching. One indexed read keeps revocation immediate. Caching can be added if load testing in M14 shows a need.
3. **Leaked-password check.** It uses Django's built-in list of about 20,000 common passwords drawn from breach data, checked offline. An online breach-database check would send hashed prefixes of passwords to a third party, so I did not add one.
4. **Implementation defaults** (not in the decision; easy to change):
   - per-address limits: 30 per 15 minutes for staff sign-in, 60 per 15 minutes for customers, 10 link requests per hour
   - customer email-verification links last 24 hours
5. **Store Admin can view the staff list**, so they can find whom they may suspend.
6. **Sign-in requests have no CSRF token,** because no session exists yet. They are protected by JSON-only requests and SameSite cookies.

## 4. Limitations and items for you

1. **Staff dashboard design.** No approved design exists for staff screens (A-04 covers the storefront). They use the A-03 tokens and are ready for your review.
2. **Customer session screen.** The API is built now; the dashboard screen is built with the account pages in M7.
3. **Recovery channels.** Email only today. SMS joins once P-08 chooses a provider.
4. **Wipe the local Docker database once** (`docker compose -f infra/compose.yaml down -v`), because M2 introduces the custom account model.
5. **CSP.** The automated check covers the sign-in pages only. Results are unchanged from V-05 run 1: only Next.js's own inline scripts. The signed-in screens use no inline scripts or styles.
6. **Email delivery.** Emails are sent by a background job after commit. The full outbox with delivery tracking comes in M8.
7. **Still open:**
   - D-09 and staging wait for P-10.
   - Passkeys come in M14.
   - No physical-device testing was done.

## 5. Next

M3 (design system and shell) needs **P-19**: the final palette and the design references. Nothing is started until you approve this report.
