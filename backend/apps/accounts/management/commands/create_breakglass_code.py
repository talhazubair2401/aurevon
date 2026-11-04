"""Create the sealed emergency code for Owner break-glass recovery (decision 0003, 4.4).
It is shown once: print it, seal it offline (for example in a safe), and never store it digitally."""

import getpass
from typing import Any

from django.core.management.base import BaseCommand

from apps.accounts.services import recovery


class Command(BaseCommand):
    help = "Create (or replace) the single-use break-glass emergency code. Shown once."

    def handle(self, *args: Any, **options: Any) -> None:
        code = recovery.create_break_glass_code(f"operator:{getpass.getuser()}")
        self.stdout.write("Break-glass emergency code (shown once; any earlier code no longer works):\n")
        self.stdout.write(f"    {code}\n")
        self.stdout.write("Seal it offline. It works once, together with access to the production server.")
