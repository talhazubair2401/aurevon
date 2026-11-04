from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"

    def ready(self) -> None:
        from . import schema  # noqa: F401  (registers the OpenAPI cookie schemes)
        from .roles import sync_system_roles

        # The six system roles always match permissions.ROLE_PERMISSIONS after every migrate.
        post_migrate.connect(sync_system_roles, sender=self, dispatch_uid="accounts.sync_system_roles")
