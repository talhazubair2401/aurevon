# Provisional settings (pending business decisions)

The platform is built so each pending decision is a **setting or data**, not code. Until the owner decides, these
provisional values apply. Staff can change every one of them in the staff dashboard (Settings) without a release.

| Decision | What it controls | Provisional value | Where |
|---|---|---|---|
| P-15 Guest checkout | Guests may check out without an account | On | Setting `checkout.guest_allowed` |
| D-06 Reservation expiry | Minutes an unpaid online order holds stock (never shorter than the provider's window + 2 min; min 30) | 30 | Setting `checkout.reservation_minutes` |
| R-08 / P-06 COD | Cash on delivery offered at checkout; optional order-value limit | On, no limit | Settings `payments.cod_enabled`, `payments.cod_max_order` |
| P-06 Online payment provider | Card/wallet payments | **Sandbox only** (simulated provider, refused in production). A real provider is one adapter in `backend/integrations/payments.py` plus credentials | Env `PAYMENTS_ONLINE_PROVIDER`, `PAYMENTS_SANDBOX_ENABLED` |
| D-07 Late payments | Payment succeeding after the order expired | As proposed in MTS §10: re-reserve and restore if stock allows, otherwise automatic refund; staff alerted either way | Code (`orders.services.confirm_paid`) |
| P-11 Tax | Rates and whether prices include tax | No tax rule: tax is zero, nothing invented. Staff add effective-dated tax rules (inclusive or exclusive) | Table `localization_taxrule` |
| P-13 Shipping | Zones, fees, free-delivery threshold, delivery promises | No real rates. Demo zones exist only in demo data (Karachi, Lahore, Islamabad/Rawalpindi, rest of Pakistan) | Tables `shipping_shippingzone`, `shipping_shippingrate` |
| P-14 Returns window | Days after delivery a return can be requested | 7 (0 turns returns off) | Setting `returns.window_days` |
| Decision 0003 §1.5 Refund approvals | Refunds above this amount need a second approver | Unset: every refund needs two approvers | Setting `refunds.dual_approval_threshold` |
| Coupons vs promotions | Stacking | No stacking: the larger discount applies | Code (`promotions.services.evaluate`) |
| P-11 Tax (staff screen) | Entering the confirmed rule | Staff › Settings › Tax; saving asks for the authenticator code; rules are ended, never edited | `/api/v1/staff/tax-rules` |
| P-13 Shipping (staff screen) | Entering real zones and rates | Staff › Settings › Delivery zones and rates | `/api/v1/staff/shipping-zones`, `/shipping-rates` |
| P-07 Couriers | Booking and tracking | Manual courier: staff enter the courier, tracking number and link; tracking updates entered by staff. A courier API is one adapter in `backend/integrations/couriers.py` | Code + env |
| P-08 SMS provider | Order-update SMS (opt-in only) | `log` adapter: nothing is sent, messages are logged (masked number). A provider is one adapter in `backend/integrations/sms.py` | Env `SMS_PROVIDER` |
| P-08 Email provider | Transactional email | SMTP settings by environment (Mailpit locally) | Env `EMAIL_*` |
| M11 Abandoned-bag reminders | When reminders go, and to whom | One email, 24 h after the bag last changed, only to signed-in customers with a verified email who opted in (Account › Details › Messages); bags older than 7 days skipped; one-click unsubscribe | Env `CART_REMINDER_AFTER_HOURS`, `CART_REMINDER_WINDOW_DAYS` |
| P-14 Return instructions | What an approved return email tells the customer | Generic packing text; courier pickup/drop-off arranged by email | Setting `returns.instructions` |
| Return refunds | Default refund amount for a return | Price of the returned items less their share of any order discount; delivery not refunded. Staff can change the amount; the refund then follows the normal approval rules | Code (`returns.services.suggested_refund`) |
| Exchanges | Replacement for a returned item | A no-charge replacement order (payment method "exchange"), confirmed at once and fulfilled like any order | Code (`returns.services.complete`) |
| P-16 Analytics definitions | What reports count | Sales = orders confirmed or later, by Pakistan day placed; gross = order totals; net = gross − refunds paid out; exchanges excluded. Storefront behavioural analytics (page views, funnels) is **not built** until P-16 sets the consent model | Code (`reports.services`) |
