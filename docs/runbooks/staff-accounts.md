# Runbook: staff accounts, recovery and break-glass

Decision record: `docs/decisions/0003-m2-identity-security.md`. Commands run in the API container
(`docker compose -f infra/compose.yaml exec api python manage.py …`) or on the production API host.

## First set-up (once per environment)

1. `python manage.py create_owner --email you@example.com --name "Your Name"`
   Emails a 48-hour set-up link. Refused once any Owner exists.
2. Open the link, set a password, scan the QR code with an authenticator app, save the 10 recovery codes offline.
3. In **Team**, invite a **second, independent Owner** (a different trusted person). Until then every staff page
   shows the single-Owner warning.
4. `python manage.py create_breakglass_code`. Print the code, seal it offline (for example in a safe). Shown once.
5. Before launch: `python manage.py security_status` must report **Ready** (two active Owners and a sealed code).

Locally, emails arrive in Mailpit: http://localhost:8025.

## Someone lost access

| Situation | What to do |
| --- | --- |
| Forgot password, still has the authenticator | They use **Forgot your password?** on the sign-in page (30-minute link and an authenticator code). |
| Lost the authenticator, has a recovery code | They sign in with password and a recovery code, then must set up a new authenticator before anything else. |
| Lost both (staff) | An Owner verifies the person **outside the system** (voice or in person), then **Team → Manage → Approve account recovery**. Their old password and authenticator stop working at once; a 30-minute link is emailed. |
| Lost both (an Owner) | Another Owner approves as above. The recovery **waits 24 hours**; every registered recovery channel gets a notice with an immediate **cancellation link**. Old credentials keep working during the wait. Afterwards a 30-minute link is emailed; **Send a new recovery link** reissues it. |
| The only Owner is locked out | Break-glass (below). |

Nobody can approve their own recovery. Support staff can't recover accounts. There is no email-only reset for staff.

## Break-glass (last resort)

Needs production server access **and** the sealed emergency code.

```
python manage.py breakglass_recover_owner --email owner@example.com --operator "Full Name"
```

It asks for the code, ends all of that Owner's sessions, invalidates their credentials, prints and emails a
30-minute recovery link, and alerts every Owner. The code is then used up: create and seal a new one immediately.

## Suspected staff account compromise

1. **Team → Manage → End all sessions** (no re-confirmation needed, so it is instant), then **Suspend** with a reason.
2. Review **Audit log** for the account (filter by action, or by the account id).
3. When safe, the account holder recovers the account (above). An Owner reactivates it.

Five failed sign-in attempts or codes in 15 minutes lock the account for 15 minutes, end its sessions and email every Owner.
