"""Bootstrap the first Owner. Refused once any Owner exists: later Owners are invited from the dashboard."""

import getpass
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from apps.accounts import policy
from apps.accounts.models import Account, AccountStatus, AccountType, Role, StaffProfile, TokenPurpose, normalize_email
from apps.accounts.permissions import RoleCode
from apps.accounts.services import notify, tokens
from apps.audit.services import Actor, record


class Command(BaseCommand):
    help = "Create the first Owner account and email its 48-hour set-up link."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", default="")

    def handle(self, *args: Any, **options: Any) -> None:
        email = normalize_email(options["email"])
        if StaffProfile.objects.filter(role_id=RoleCode.OWNER).exists():
            raise CommandError("An Owner already exists. Invite further Owners from the staff dashboard.")
        operator = getpass.getuser()
        with transaction.atomic():
            account = Account.objects.create(
                email=email, account_type=AccountType.STAFF, status=AccountStatus.INVITED, full_name=options["name"]
            )
            account.set_unusable_password()
            account.save(update_fields=["password"])
            StaffProfile.objects.create(account=account, role=Role.objects.get(code=RoleCode.OWNER))
            value = tokens.issue(account, TokenPurpose.STAFF_INVITE, policy.STAFF_INVITE_LIFETIME)
            notify.to_account(
                account,
                "staff_invite",
                link=tokens.staff_link("enroll", value),
                role="Owner",
                invited_by="AureVon set-up",
                hours=48,
            )
            record(
                "staff.owner_bootstrapped",
                Actor(None, f"operator:{operator}"),
                target_type="account",
                target_id=account.pk,
            )
        self.stdout.write(
            self.style.SUCCESS(f"Owner {email} created. The set-up link has been emailed (valid 48 hours).")
        )
