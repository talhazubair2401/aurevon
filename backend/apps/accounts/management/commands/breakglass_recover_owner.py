"""Last-resort Owner recovery (decision 0003, 4.4). Needs production server access (to run this) and the
sealed emergency code. Issues a 30-minute recovery link, ends all sessions and alerts every Owner."""

import getpass
import sys
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accounts.services import recovery
from common.exceptions import ApiProblem


class Command(BaseCommand):
    help = "Recover an Owner account with the sealed break-glass code."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--email", required=True)
        parser.add_argument("--operator", required=True, help="Full name of the person running this, for the audit log")
        parser.add_argument("--code-stdin", action="store_true", help="Read the emergency code from standard input")

    def handle(self, *args: Any, **options: Any) -> None:
        code = sys.stdin.readline().strip() if options["code_stdin"] else getpass.getpass("Emergency code: ")
        label = f"{options['operator']} (os user {getpass.getuser()})"
        try:
            link = recovery.break_glass_recover(options["email"], code, label)
        except ApiProblem as exc:
            raise CommandError(str(exc.detail)) from exc
        self.stdout.write(self.style.SUCCESS("Recovery released. Every Owner has been alerted."))
        self.stdout.write(f"Recovery link (single-use, 30 minutes; also emailed to the account):\n    {link}")
        self.stdout.write("Create a new sealed code now: python manage.py create_breakglass_code")
