from django.apps import AppConfig


class SandboxConfig(AppConfig):
    name = "apps.sandbox"
    label = "sandbox"
    default_auto_field = "django.db.models.BigAutoField"
