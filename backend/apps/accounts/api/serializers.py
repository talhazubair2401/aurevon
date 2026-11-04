from typing import Any

from rest_framework import serializers

from .. import policy


class EmailPasswordIn(serializers.Serializer[Any]):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=policy.PASSWORD_MAX * 2, trim_whitespace=False)


class ChallengeOut(serializers.Serializer[Any]):
    challenge = serializers.CharField()
    expires_in = serializers.IntegerField()


class MfaVerifyIn(serializers.Serializer[Any]):
    challenge = serializers.CharField(max_length=200)
    code = serializers.CharField(max_length=10, required=False, allow_blank=True)
    recovery_code = serializers.CharField(max_length=20, required=False, allow_blank=True)


class CodeIn(serializers.Serializer[Any]):
    code = serializers.CharField(max_length=10)


class EmailIn(serializers.Serializer[Any]):
    email = serializers.EmailField(max_length=254)


class TokenIn(serializers.Serializer[Any]):
    token = serializers.CharField(max_length=200)


class TokenPasswordIn(TokenIn):
    password = serializers.CharField(max_length=policy.PASSWORD_MAX * 2, trim_whitespace=False)


class TokenPasswordCodeIn(TokenPasswordIn):
    code = serializers.CharField(max_length=10)


class PendingDeviceOut(serializers.Serializer[Any]):
    email = serializers.EmailField()
    secret = serializers.CharField(help_text="Base32 secret, for manual entry in the authenticator app.")
    otpauth_uri = serializers.CharField()
    qr_svg = serializers.CharField(help_text="The otpauth URI as an inline SVG QR code.")


class RoleOut(serializers.Serializer[Any]):
    code = serializers.CharField()
    name = serializers.CharField()


class RoleWithPermissionsOut(RoleOut):
    permissions = serializers.ListField(child=serializers.CharField())


class StaffAccountSummaryOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    status = serializers.CharField()
    role = RoleOut()


class StaffSessionMetaOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    expires_at = serializers.DateTimeField()
    idle_timeout_seconds = serializers.IntegerField()
    stepped_up_until = serializers.DateTimeField(allow_null=True)
    mfa_reenrollment_required = serializers.BooleanField()


class OwnRecoveryOut(serializers.Serializer[Any]):
    status = serializers.CharField()
    effective_at = serializers.DateTimeField()
    approved_by = serializers.CharField()


class StaffSessionInfoOut(serializers.Serializer[Any]):
    account = StaffAccountSummaryOut()
    permissions = serializers.ListField(child=serializers.CharField())
    csrf_token = serializers.CharField()
    session = StaffSessionMetaOut()
    security_warnings = serializers.ListField(
        child=serializers.ChoiceField(choices=["single_owner", "few_recovery_codes"])
    )
    recovery_in_progress = OwnRecoveryOut(allow_null=True)


class SetupCompleteOut(serializers.Serializer[Any]):
    session = StaffSessionInfoOut()
    recovery_codes = serializers.ListField(child=serializers.CharField())


class RecoveryCodesOut(serializers.Serializer[Any]):
    recovery_codes = serializers.ListField(child=serializers.CharField())


class StepUpOut(serializers.Serializer[Any]):
    stepped_up_until = serializers.DateTimeField()


class SessionOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    last_seen_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    ip = serializers.IPAddressField(allow_null=True)
    user_agent = serializers.CharField()
    current = serializers.BooleanField()


class ChangePasswordIn(serializers.Serializer[Any]):
    current_password = serializers.CharField(max_length=policy.PASSWORD_MAX * 2, trim_whitespace=False)
    new_password = serializers.CharField(max_length=policy.PASSWORD_MAX * 2, trim_whitespace=False)


class RecoveryEmailIn(serializers.Serializer[Any]):
    recovery_email = serializers.EmailField(max_length=254, allow_blank=True)


class RecoveryEmailOut(serializers.Serializer[Any]):
    recovery_email = serializers.CharField()


class InviteIn(serializers.Serializer[Any]):
    email = serializers.EmailField(max_length=254)
    full_name = serializers.CharField(max_length=150)
    role = serializers.CharField(max_length=40)


class RoleChangeIn(serializers.Serializer[Any]):
    role = serializers.CharField(max_length=40)


class SuspendIn(serializers.Serializer[Any]):
    reason = serializers.CharField(max_length=300)


class StaffRecoveryStateOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    status = serializers.CharField()
    effective_at = serializers.DateTimeField()
    approved_by = serializers.CharField()
    created_at = serializers.DateTimeField()


class StaffAccountDetailOut(StaffAccountSummaryOut):
    created_at = serializers.DateTimeField()
    last_login = serializers.DateTimeField(allow_null=True)
    invited_by = serializers.EmailField(allow_null=True)
    active_sessions = serializers.IntegerField()
    has_authenticator = serializers.BooleanField()
    recovery_codes_remaining = serializers.IntegerField()
    recovery = StaffRecoveryStateOut(allow_null=True)


class RevokedOut(serializers.Serializer[Any]):
    revoked = serializers.IntegerField()


class CustomerRegisterIn(EmailPasswordIn):
    full_name = serializers.CharField(max_length=150, allow_blank=True, required=False, default="")


class CustomerSignInIn(EmailPasswordIn):
    remember = serializers.BooleanField(default=False)


class CustomerAccountOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    email_verified = serializers.BooleanField()


class CustomerSessionInfoOut(serializers.Serializer[Any]):
    account = CustomerAccountOut()
    csrf_token = serializers.CharField()
    session = SessionOut()


class AcceptedOut(serializers.Serializer[Any]):
    detail = serializers.CharField()
