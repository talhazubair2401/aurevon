from typing import Any

from django.db import transaction

from apps.audit.services import Actor, record

from .models import StoreSetting
from .settings_registry import SETTINGS, SettingSpec


class UnknownSetting(KeyError):
    pass


def spec_for(key: str) -> SettingSpec:
    try:
        return SETTINGS[key]
    except KeyError as exc:
        raise UnknownSetting(key) from exc


def get_value(key: str) -> Any:
    spec = spec_for(key)
    row = StoreSetting.objects.filter(key=key).first()
    return spec.default if row is None else row.value


def all_values() -> dict[str, Any]:
    stored = {row.key: row.value for row in StoreSetting.objects.all()}
    return {key: stored.get(key, spec.default) for key, spec in SETTINGS.items()}


@transaction.atomic
def set_value(key: str, raw: Any, actor: Actor, request: Any = None) -> Any:
    """Validates, stores and audits one setting. Raises ValueError with a readable message."""
    spec = spec_for(key)
    value = spec.validate(raw)
    before = get_value(key)
    StoreSetting.objects.update_or_create(key=key, defaults={"value": value, "updated_by_id": actor.id})
    record(
        "settings.change",
        actor,
        target_type="setting",
        target_id=key,
        before={"value": before},
        after={"value": value},
        request=request,
    )
    return value
