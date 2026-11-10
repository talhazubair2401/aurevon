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
