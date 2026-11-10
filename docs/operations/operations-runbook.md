# Day-to-day operations

## Where things happen (staff dashboard)

| Task | Screen | Who (decision 0003) |
|---|---|---|
| Pack, dispatch, add tracking, mark delivered | Orders › order | orders.update (Owner, Store Admin, Support) |
| Record COD money from the courier | Orders › order › Cash on delivery | remittance.reconcile (Owner, Accountant) |
| Request a refund | Orders › order, or Support › Returns | refunds.request (asks for the authenticator code) |
| Approve refunds | Orders › Refunds | refunds.approve (Owner, Accountant); requester can't approve their own |
| Answer customers | Support › Messages | tickets.handle |
| Returns and exchanges | Support › Returns | returns.decide |
| Stock corrections, quarantine | Inventory | inventory.adjust / inventory.inspect |
| Purchase orders | Inventory › Purchase orders | purchase_orders.manage |
| Coupons, promotions | Marketing | promotions.edit |
| Delivery zones, tax | Settings | settings.store (tax asks for the authenticator code) |
| Reports, CSV | Reports | reports.aggregate; customer-detail CSV: reports.export_personal (audited) |

## Alerts and what to do

| Alert | Meaning | Action |
|---|---|---|
| stock_low | sellable stock at or below the reorder level | raise a purchase order; clears itself when stock recovers |
| cod_discrepancy | courier paid a different amount | check the courier statement; record the note to reconcile |
| delivery_failed | courier couldn't deliver | contact the customer; next tracking update or return |
| late-payment-* | a payment arrived after the order expired | restored automatically, or refunded automatically |
| refund failed / manual required | the provider refused the refund | pay manually and record the reference |
| return_requested, ticket_new, ticket_reply | customer is waiting | Support dashboard |

## Scheduled jobs (scheduler service)

Every minute: payment status checks, unpaid order expiry, owner recovery release. Every 5 minutes: refund retries.
Every 15 minutes: consented bag reminders. If the scheduler is down, payments still confirm by webhook, but expiry,
retries and reminders pause: restart it, and check `celery inspect active` on the worker.

## Incidents

- Payments failing: check the provider status page; card checkout can be switched off by disabling the provider;
  COD continues (`payments.cod_enabled`).
- Email not arriving: Mailpit/SMTP credentials; the outbox retries 5 times with backoff.
- Suspected account compromise: Team › member › Suspend (ends every session at once); see
  `docs/runbooks/staff-accounts.md`. The audit log shows who did what.
