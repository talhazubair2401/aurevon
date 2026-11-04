"""Model -> response dictionaries, shared by the views."""

from typing import Any

from ..models import (
    Account,
    CustomerSession,
    SessionBase,
    StaffProfile,
    StaffRecoveryRequest,
    StaffSession,
)
from ..policy import STEP_UP_VALIDITY
from ..services import access, mfa, recovery, sessions

LOW_RECOVERY_CODES = 3


def role(profile: StaffProfile) -> dict[str, str]:
    return {"code": profile.role.code, "name": profile.role.name}


def staff_summary(account: Account, profile: StaffProfile | None = None) -> dict[str, Any]:
    profile = profile or StaffProfile.objects.select_related("role").get(account=account)
    return {
        "id": account.pk,
        "email": account.email,
        "full_name": account.full_name,
        "status": account.status,
        "role": role(profile),
    }


def recovery_state(req: StaffRecoveryRequest | None) -> dict[str, Any] | None:
    if req is None:
        return None
    return {
        "id": req.id,
        "status": req.status,
        "effective_at": req.effective_at,
        "approved_by": req.approved_by_label,
        "created_at": req.created_at,
    }


def staff_session_info(session: StaffSession) -> dict[str, Any]:
    account = session.account
    warnings = []
    if access.active_owner_count() < 2:
        warnings.append("single_owner")  # decision 0003, clarification 1: persistent until a second Owner exists
    if mfa.remaining_recovery_codes(account) <= LOW_RECOVERY_CODES:
        warnings.append("few_recovery_codes")
    own = recovery.open_request(account)
    return {
        "account": staff_summary(account),
        "permissions": sorted(access.permissions_for(account)),
        "csrf_token": session.csrf_token,
        "session": {
            "id": session.id,
            "expires_at": session.expires_at,
            "idle_timeout_seconds": session.idle_timeout_seconds,
            "stepped_up_until": session.stepped_up_at + STEP_UP_VALIDITY if session.stepped_up_at else None,
            "mfa_reenrollment_required": session.mfa_reenrollment_required,
        },
        "security_warnings": warnings,
        "recovery_in_progress": (
            {"status": own.status, "effective_at": own.effective_at, "approved_by": own.approved_by_label}
            if own
            else None
        ),
    }


def session_row(row: SessionBase, current: SessionBase | None) -> dict[str, Any]:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "last_seen_at": row.last_seen_at,
        "expires_at": row.expires_at,
        "ip": row.ip,
        "user_agent": row.user_agent,
        "current": current is not None and row.pk == current.pk,
    }


def staff_detail(account: Account) -> dict[str, Any]:
    profile = StaffProfile.objects.select_related("role", "invited_by").get(account=account)
    return {
        **staff_summary(account, profile),
        "created_at": account.created_at,
        "last_login": account.last_login,
        "invited_by": profile.invited_by.email if profile.invited_by else None,
        "active_sessions": len(sessions.live_sessions(sessions.STAFF, account)),
        "has_authenticator": mfa.confirmed_device(account) is not None,
        "recovery_codes_remaining": mfa.remaining_recovery_codes(account),
        "recovery": recovery_state(recovery.open_request(account)),
    }


def customer_session_info(session: CustomerSession) -> dict[str, Any]:
    account = session.account
    return {
        "account": {
            "id": account.pk,
            "email": account.email,
            "full_name": account.full_name,
            "email_verified": account.email_verified_at is not None,
        },
        "csrf_token": session.csrf_token,
        "session": session_row(session, session),
    }
