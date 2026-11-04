"""Launch-readiness security checks (decision 0003, clarification 1). Exits non-zero when not ready.
Part of the launch checklist (M15)."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import BreakGlassCredential
from apps.accounts.services import access


class Command(BaseCommand):
    help = "Check identity security requirements for production launch."

    def handle(self, *args: Any, **options: Any) -> None:
        problems = []
        owners = access.active_owner_count()
        if owners < 2:
            problems.append(
                f"Only {owners} active Owner account(s); a second, independent Owner is required before launch."
            )
        if not BreakGlassCredential.objects.filter(used_at__isnull=True, retired_at__isnull=True).exists():
            problems.append("No sealed break-glass code exists (python manage.py create_breakglass_code).")
        if problems:
            raise CommandError("Not ready for launch:\n- " + "\n- ".join(problems))
        self.stdout.write(self.style.SUCCESS(f"Ready: {owners} active Owners and a sealed break-glass code."))
