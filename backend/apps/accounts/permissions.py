"""Staff permissions and the six fixed roles (decision 0003, section 1; MTS §9 candidate matrix).

This file is the single source of truth. On every migrate, the system roles in the database are
made to match it exactly (`roles.sync_system_roles`), and tests pin the matrix cell by cell.
Permissions for modules built later are declared now so that the matrix is complete and reviewable;
each becomes enforceable when its endpoints are built."""

from enum import StrEnum


class Perm(StrEnum):
    # Administration (M2)
    STAFF_VIEW = "staff.view"
    STAFF_INVITE = "staff.invite"
    STAFF_MANAGE_ROLES = "staff.manage_roles"
    STAFF_SUSPEND = "staff.suspend"  # staff other than Owners and Store Admins
    STAFF_SUSPEND_PRIVILEGED = "staff.suspend_privileged"  # Owners and Store Admins too
    STAFF_REACTIVATE = "staff.reactivate"
    STAFF_DEACTIVATE = "staff.deactivate"
    STAFF_RECOVER = "staff.recover"
    AUDIT_VIEW = "audit.view"
    SETTINGS_STORE = "settings.store"
    SETTINGS_SECURITY = "settings.security"
    # Catalogue and prices (M5)
    CATALOG_VIEW = "catalog.view"
    CATALOG_EDIT = "catalog.edit"
    CATALOG_PUBLISH = "catalog.publish"
    PRICES_VIEW = "prices.view"
    PRICES_EDIT = "prices.edit"
    # Inventory and suppliers (M9)
    INVENTORY_VIEW = "inventory.view"
    INVENTORY_ADJUST = "inventory.adjust"
    INVENTORY_INSPECT = "inventory.inspect"
    PURCHASE_ORDERS_MANAGE = "purchase_orders.manage"
    # Orders, refunds, remittance (M8, M10)
    ORDERS_VIEW = "orders.view"
    ORDERS_UPDATE = "orders.update"
    REFUNDS_REQUEST = "refunds.request"
    REFUNDS_APPROVE = "refunds.approve"
    REMITTANCE_VIEW = "remittance.view"
    REMITTANCE_RECONCILE = "remittance.reconcile"
    # Customer care (M12)
    RETURNS_VIEW = "returns.view"
    RETURNS_DECIDE = "returns.decide"
    TICKETS_VIEW = "tickets.view"
    TICKETS_HANDLE = "tickets.handle"
    # Content and marketing (M4, M11)
    CMS_EDIT = "cms.edit"
    CMS_PUBLISH = "cms.publish"
    SEO_EDIT = "seo.edit"
    PROMOTIONS_EDIT = "promotions.edit"
    # Reports (M13)
    REPORTS_AGGREGATE = "reports.aggregate"
    REPORTS_EXPORT_PERSONAL = "reports.export_personal"


class RoleCode(StrEnum):
    OWNER = "owner"
    STORE_ADMIN = "store_admin"
    ACCOUNTANT = "accountant"
    INVENTORY_MANAGER = "inventory_manager"
    SUPPORT = "support"
    CONTENT_MARKETING = "content_marketing"


ROLE_NAMES: dict[RoleCode, str] = {
    RoleCode.OWNER: "Owner",
    RoleCode.STORE_ADMIN: "Store Admin",
    RoleCode.ACCOUNTANT: "Accountant",
    RoleCode.INVENTORY_MANAGER: "Inventory Manager",
    RoleCode.SUPPORT: "Support",
    RoleCode.CONTENT_MARKETING: "Content / Marketing",
}

# Roles whose holders only an Owner may suspend or revoke (decision 0003, 1.3).
PRIVILEGED_ROLES = frozenset({RoleCode.OWNER, RoleCode.STORE_ADMIN})

P = Perm
ROLE_PERMISSIONS: dict[RoleCode, frozenset[Perm]] = {
    RoleCode.OWNER: frozenset(Perm),
    RoleCode.STORE_ADMIN: frozenset(
        {
            P.STAFF_VIEW,
            P.STAFF_SUSPEND,
            P.AUDIT_VIEW,
            P.SETTINGS_STORE,
            P.CATALOG_VIEW,
            P.CATALOG_EDIT,
            P.CATALOG_PUBLISH,
            P.PRICES_VIEW,
            P.PRICES_EDIT,
            P.INVENTORY_VIEW,
            P.ORDERS_VIEW,
            P.ORDERS_UPDATE,
            P.REFUNDS_REQUEST,
            P.REMITTANCE_VIEW,
            P.RETURNS_VIEW,
            P.RETURNS_DECIDE,
            P.TICKETS_VIEW,
            P.TICKETS_HANDLE,
            P.CMS_EDIT,
            P.CMS_PUBLISH,
            P.SEO_EDIT,
            P.PROMOTIONS_EDIT,
            P.REPORTS_AGGREGATE,
        }
    ),
    RoleCode.ACCOUNTANT: frozenset(
        {
            P.AUDIT_VIEW,
            P.PRICES_VIEW,
            P.INVENTORY_VIEW,
            P.ORDERS_VIEW,
            P.REFUNDS_APPROVE,
            P.REMITTANCE_VIEW,
            P.REMITTANCE_RECONCILE,
            P.RETURNS_VIEW,
            P.TICKETS_VIEW,
            P.REPORTS_AGGREGATE,
            P.REPORTS_EXPORT_PERSONAL,
        }
    ),
    RoleCode.INVENTORY_MANAGER: frozenset(
        {
            P.CATALOG_VIEW,
            P.INVENTORY_VIEW,
            P.INVENTORY_ADJUST,
            P.INVENTORY_INSPECT,
            P.PURCHASE_ORDERS_MANAGE,
            P.ORDERS_VIEW,
        }
    ),
    RoleCode.SUPPORT: frozenset(
        {
            P.CATALOG_VIEW,
            P.ORDERS_VIEW,
            P.ORDERS_UPDATE,
            P.REFUNDS_REQUEST,
            P.RETURNS_VIEW,
            P.RETURNS_DECIDE,
            P.TICKETS_VIEW,
            P.TICKETS_HANDLE,
        }
    ),
    RoleCode.CONTENT_MARKETING: frozenset(
        {P.CATALOG_VIEW, P.CATALOG_EDIT, P.CMS_EDIT, P.CMS_PUBLISH, P.SEO_EDIT, P.PROMOTIONS_EDIT}
    ),
}
