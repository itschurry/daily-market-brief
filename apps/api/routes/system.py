from __future__ import annotations

from services.notification_service import get_notification_service
from services.system_mode_service import get_mode_status


def handle_system_mode() -> tuple[int, dict]:
    try:
        return 200, get_mode_status()
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}


def handle_notifications_status() -> tuple[int, dict]:
    try:
        status = get_notification_service().status()
        return 200, {"ok": True, **status}
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}
