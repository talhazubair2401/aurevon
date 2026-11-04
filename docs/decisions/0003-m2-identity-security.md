# 0003 — M2 identity and security decisions (P-05, D-12)

Date: 4 November 2026 · Decided by: Talha (product owner) · Blueprint: MTS v2.1 §9 · Status: **APPROVED**

Approved as recommended, with the three clarifications marked **(clarified)**. These close P-05 and D-12.

## 1. Staff roles and permissions (P-05)

| # | Decision |
| --- | --- |
| 1.1 | Six fixed roles at launch: Owner, Store Admin, Accountant, Inventory Manager, Support, Content/Marketing. Exactly one role per staff account. Custom roles are post-launch. |
| 1.2 | Roles are sets of named permissions. Default deny; checked on every request. Django's `is_superuser` grants nothing. |
| 1.3 | Store Admin: may suspend staff and revoke their sessions, except Owner and Store Admin accounts; only an Owner reactivates. May change store and content settings, never security, payment, staff or role settings. Aggregate reports only, no exports with personal data. |
| 1.4 | Refunds: Store Admin and Support request; Accountant and Owner approve. |
| 1.5 | Nobody approves their own request (refunds, assisted recovery). Refunds above a threshold need a second approver (Accountant and Owner). The threshold is a store setting built in M2; its amount is decided at M8. |
| 1.6 | All other cells of the MTS §9 candidate matrix are approved unchanged. |

## 2. Two-factor authentication

| # | Decision |
| --- | --- |
| 2.1 | Authenticator app (TOTP) mandatory for every staff account, enrolled at first sign-in. No SMS or email codes for staff. |
| 2.2 | Owners: the same, plus re-confirmation for every high-risk action. Passkeys / security keys are added in M14. |
| 2.3 | 10 single-use recovery codes, stored hashed, shown once; regenerating cancels the old set. |
| 2.4 | A used code can't be reused. 5 wrong codes lock the account for 15 minutes and alert Owners. |
| 2.5 | Re-confirmation (valid 5 minutes) for refunds, price changes, role and permission changes, suspensions and recovery approvals. |

## 3. Sessions and account security

| # | Decision |
| --- | --- |
| 3.1 | Staff: 30-minute idle timeout, 12-hour absolute maximum. |
| 3.2 | Customers: without "remember me", the session ends with the browser (24-hour server cap); with it, 30 days rolling, 90 days absolute. |
| 3.3 | Suspension, password change, new authenticator and recovery revoke sessions immediately. Staff can see and end their own sessions. |
| 3.3a **(clarified)** | **Customers can also view and revoke their own active sessions from their account dashboard.** (API in M2; the dashboard screen is built with the account pages in M7.) |
| 3.4 | Staff: 5 failures in 15 minutes lock for 15 minutes, plus a per-network-address limit; Owners alerted. Customers: growing delays plus a per-address limit, no hard lockout. The same response whether or not an account exists. |
| 3.5 | Passwords: staff at least 12 characters, customers at least 10, up to 128; common and leaked passwords blocked; no forced rotation; Argon2. |
| 3.6 | Single-use links: staff invite 48 hours, password reset 30 minutes, recovery 30 minutes. |

## 4. Owner account recovery (D-12)

| # | Decision |
| --- | --- |
| 4.1 **(clarified)** | **Initial setup with one Owner is allowed, with a persistent security warning in the staff dashboard. A second, independent Owner is required before normal production launch** (checked by `manage.py security_status`, part of the launch checklist). The last active Owner can't be suspended, deactivated or demoted. |
| 4.2 | First option: the Owner's own offline recovery codes. |
| 4.3 **(clarified)** | Second option: another Owner verifies the person outside the system and approves with their own code; recovery takes effect after a **24-hour waiting period**. **During the wait, the affected Owner is notified through every registered recovery channel, and each notification carries an immediate cancellation link.** Any Owner can also cancel from the dashboard. |
| 4.4 | Last resort: an audited break-glass management command needing both production server access and a sealed, offline emergency code; it issues a 30-minute single-use recovery link, revokes sessions and alerts every Owner. |
| 4.5 | Never: email-only recovery, Django admin, or recovery by support staff. |

Not decided here: D-09 (network restriction for staff routes) — needed only when staff routes go on staging (P-10).
