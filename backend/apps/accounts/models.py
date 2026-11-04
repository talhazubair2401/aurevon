"""Customer and staff identities, kept strictly apart (MTS v2.1 A-22, §6 Identity, §9)."""

import uuid
from typing import Any, ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class AccountType(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    STAFF = "staff", "Staff"


class AccountStatus(models.TextChoices):
    INVITED = "invited", "Invited"  # staff only, until enrollment completes
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    DEACTIVATED = "deactivated", "Deactivated"


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AccountManager(BaseUserManager["Account"]):
    def get_for(self, email: str, account_type: str) -> "Account | None":
        return self.filter(email=normalize_email(email), account_type=account_type).first()


class Account(AbstractBaseUser):
    """One sign-in identity. The type is fixed at creation; the same email may hold one customer and one
    staff account, which never share sessions. There is deliberately no `is_superuser` / `is_staff`."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254)
    account_type = models.CharField(max_length=16, choices=AccountType.choices)
    status = models.CharField(max_length=16, choices=AccountStatus.choices, default=AccountStatus.ACTIVE)
    full_name = models.CharField(max_length=150, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"  # unique together with account_type, not alone
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["account_type"]

    objects = AccountManager()

    class Meta:
        constraints: ClassVar[list[Any]] = [
            models.UniqueConstraint(fields=["email", "account_type"], name="account_email_type_unique"),
            models.CheckConstraint(condition=Q(account_type__in=AccountType.values), name="account_type_valid"),
            models.CheckConstraint(condition=Q(status__in=AccountStatus.values), name="account_status_valid"),
            models.CheckConstraint(condition=Q(email=Lower("email")), name="account_email_lowercase"),
            models.CheckConstraint(
                condition=Q(account_type=AccountType.STAFF) | ~Q(status=AccountStatus.INVITED),
                name="account_invited_is_staff",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.email} ({self.account_type})"

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return self.status == AccountStatus.ACTIVE

    @property
    def is_staff_account(self) -> bool:
        return self.account_type == AccountType.STAFF


class Role(models.Model):
    """A fixed staff role. Its permissions are synchronised from `permissions.ROLE_PERMISSIONS` on migrate."""

    code = models.CharField(primary_key=True, max_length=40)
    name = models.CharField(max_length=80)
    is_system = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissions")
    permission = models.CharField(max_length=60)

    class Meta:
        constraints: ClassVar[list[Any]] = [
            models.UniqueConstraint(fields=["role", "permission"], name="role_permission_unique")
        ]

    def __str__(self) -> str:
        return f"{self.role_id}: {self.permission}"


class StaffProfile(models.Model):
    """Staff-only data. Exactly one role per staff account (decision 0003, 1.1)."""

    account = models.OneToOneField(Account, primary_key=True, on_delete=models.PROTECT, related_name="staff")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="members")
    recovery_email = models.EmailField(max_length=254, blank=True)  # optional second recovery channel
    invited_by = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    def __str__(self) -> str:
        return f"{self.account.email}: {self.role_id}"


class StaffMFADevice(models.Model):
    """An authenticator app (TOTP). The shared secret is encrypted at rest. Pending until confirmed."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="mfa_devices")
    secret_encrypted = models.TextField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_used_step = models.BigIntegerField(default=0)  # a code's time step can never be used twice
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints: ClassVar[list[Any]] = [
            models.UniqueConstraint(
                fields=["account"], condition=Q(confirmed_at__isnull=False), name="one_confirmed_mfa_device"
            )
        ]

    def __str__(self) -> str:
        return f"TOTP for {self.account_id}"


class StaffRecoveryCode(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="recovery_codes")
    code_hash = models.CharField(max_length=64, unique=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Recovery code for {self.account_id}"


class SessionBase(models.Model):
    """A server-side session: one revocable row. The cookie holds a random token; only its hash is stored."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    csrf_token = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField()
    idle_timeout_seconds = models.PositiveIntegerField()
    expires_at = models.DateTimeField()  # absolute limit
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=40, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)

    class Meta:
        abstract = True


class StaffSession(SessionBase):
    stepped_up_at = models.DateTimeField(null=True, blank=True)  # last second-factor re-confirmation
    # Signed in with a recovery code: may only enrol a new authenticator (MTS §9 recovery).
    mfa_reenrollment_required = models.BooleanField(default=False)

    class Meta:
        indexes: ClassVar[list[Any]] = [models.Index(fields=["account", "revoked_at"])]

    def __str__(self) -> str:
        return f"Staff session {self.id}"


class CustomerSession(SessionBase):
    persistent = models.BooleanField(default=False)  # "remember me"

    class Meta:
        indexes: ClassVar[list[Any]] = [models.Index(fields=["account", "revoked_at"])]

    def __str__(self) -> str:
        return f"Customer session {self.id}"


class TokenPurpose(models.TextChoices):
    STAFF_INVITE = "staff_invite"
    STAFF_PASSWORD_RESET = "staff_password_reset"  # noqa: S105  # nosec B105
    STAFF_RECOVERY = "staff_recovery"
    STAFF_RECOVERY_CANCEL = "staff_recovery_cancel"  # sent to every recovery channel during the wait
    CUSTOMER_VERIFY_EMAIL = "customer_verify_email"
    CUSTOMER_PASSWORD_RESET = "customer_password_reset"  # noqa: S105  # nosec B105


class RecoveryStatus(models.TextChoices):
    WAITING = "waiting", "Waiting"  # Owner recovery: the 24-hour wait (D-12, 4.3)
    RELEASED = "released", "Released"  # old credentials invalidated; recovery link sent
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class StaffRecoveryRequest(models.Model):
    """Assisted or break-glass recovery of a staff account that lost both password and authenticator."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="recovery_requests")
    approved_by = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    approved_by_label = models.CharField(max_length=254)  # "break-glass operator" when approved_by is empty
    created_at = models.DateTimeField(auto_now_add=True)
    effective_at = models.DateTimeField()  # when the recovery may proceed
    status = models.CharField(max_length=16, choices=RecoveryStatus.choices, default=RecoveryStatus.WAITING)
    released_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    cancelled_by_label = models.CharField(max_length=254, blank=True)

    class Meta:
        constraints: ClassVar[list[Any]] = [
            models.CheckConstraint(condition=Q(status__in=RecoveryStatus.values), name="recovery_status_valid"),
            models.UniqueConstraint(
                fields=["account"],
                condition=Q(status__in=["waiting", "released"]),
                name="one_open_recovery_per_account",
            ),
            models.CheckConstraint(condition=~Q(approved_by=models.F("account")), name="recovery_not_self_approved"),
        ]

    def __str__(self) -> str:
        return f"Recovery of {self.account_id} ({self.status})"


class AccountToken(models.Model):
    """A single-use, expiring link token. Only its hash is stored."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="tokens")
    purpose = models.CharField(max_length=32, choices=TokenPurpose.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    recovery_request = models.ForeignKey(
        StaffRecoveryRequest, null=True, blank=True, on_delete=models.CASCADE, related_name="tokens"
    )

    class Meta:
        constraints: ClassVar[list[Any]] = [
            models.CheckConstraint(condition=Q(purpose__in=TokenPurpose.values), name="token_purpose_valid")
        ]
        indexes: ClassVar[list[Any]] = [models.Index(fields=["account", "purpose"])]

    def __str__(self) -> str:
        return f"{self.purpose} for {self.account_id}"


class BreakGlassCredential(models.Model):
    """The sealed, offline emergency code for Owner recovery (D-12, 4.4). Single-use; only its hash is stored."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by_label = models.CharField(max_length=254)
    used_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Break-glass credential {self.created_at:%Y-%m-%d}"
