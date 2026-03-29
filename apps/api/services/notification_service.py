from __future__ import annotations

import asyncio
import datetime
import threading
from typing import Any

from loguru import logger

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, settings
from reporter.telegram_sender import send_text_message


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


class TelegramNotifier:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_error = ""
        self._last_sent_at = ""

    @property
    def enabled(self) -> bool:
        return _as_bool(getattr(settings, "telegram_enabled", False), False)

    @property
    def configured(self) -> bool:
        return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

    def _run_coroutine(self, coro) -> bool:
        try:
            return bool(asyncio.run(coro))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                return bool(loop.run_until_complete(coro))
            finally:
                loop.close()
                asyncio.set_event_loop(None)

    def send_message(self, message: str) -> bool:
        if not self.enabled:
            return False
        if not self.configured:
            with self._lock:
                self._last_error = "telegram_not_configured"
            logger.warning("텔레그램 알림 비활성화 또는 설정 누락으로 발송을 건너뜁니다.")
            return False
        try:
            sent = self._run_coroutine(send_text_message(message))
            with self._lock:
                if sent:
                    self._last_sent_at = _now_iso()
                    self._last_error = ""
            return sent
        except Exception as exc:
            logger.warning("텔레그램 알림 전송 실패: {}", exc)
            with self._lock:
                self._last_error = str(exc)
            return False

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "channel": "telegram",
                "enabled": self.enabled,
                "configured": self.configured,
                "chat_id_configured": bool(TELEGRAM_CHAT_ID),
                "last_sent_at": self._last_sent_at,
                "last_error": self._last_error,
            }

    def notify_engine_started(self, payload: dict[str, Any]) -> None:
        markets = payload.get("markets") or []
        interval = payload.get("interval_seconds")
        message = (
            "[투자도우미] 모의투자 엔진 시작\n"
            f"시각: {_now_iso()}\n"
            f"주기(초): {interval}\n"
            f"대상시장: {', '.join(markets) if isinstance(markets, list) and markets else '-'}"
        )
        self.send_message(message)

    def notify_engine_stopped(self, payload: dict[str, Any]) -> None:
        message = (
            "[투자도우미] 모의투자 엔진 중지\n"
            f"시각: {_now_iso()}\n"
            f"사유: {payload.get('reason') or 'manual_stop'}"
        )
        self.send_message(message)

    def notify_engine_paused(self) -> None:
        self.send_message(f"[투자도우미] 모의투자 엔진 일시정지\n시각: {_now_iso()}")

    def notify_engine_resumed(self) -> None:
        self.send_message(f"[투자도우미] 모의투자 엔진 재개\n시각: {_now_iso()}")

    def notify_engine_error(self, *, error: str, cycle_id: str) -> None:
        message = (
            "[투자도우미] 엔진 오류\n"
            f"시각: {_now_iso()}\n"
            f"오류: {error}\n"
            f"마지막 cycle: {cycle_id or '-'}"
        )
        self.send_message(message)

    def notify_order_failure(self, payload: dict[str, Any]) -> None:
        message = (
            "[투자도우미] 주문 실패\n"
            f"종목: {payload.get('code') or '-'} ({payload.get('market') or '-'})\n"
            f"side: {payload.get('side') or '-'}\n"
            f"사유: {payload.get('failure_reason') or '-'}\n"
            f"cycle: {payload.get('originating_cycle_id') or '-'}"
        )
        self.send_message(message)

    def notify_daily_loss_limit(self, payload: dict[str, Any]) -> None:
        message = (
            "[투자도우미] 일일 손실 한도 초과\n"
            f"시각: {_now_iso()}\n"
            f"일일 손실 잔여: {payload.get('daily_loss_left')}\n"
            f"사유: {payload.get('reason') or 'daily_loss_limit_reached'}"
        )
        self.send_message(message)

    def notify_order_filled(self, event: dict[str, Any], cycle_id: str = "") -> None:
        side = "모의매수" if str(event.get("side")).lower() == "buy" else "모의매도"
        message = (
            f"[투자도우미] {side} 체결\n"
            f"종목: {event.get('name') or event.get('code') or '-'} ({event.get('code') or '-'})\n"
            f"시장: {event.get('market') or '-'}\n"
            f"수량: {event.get('quantity') or 0}\n"
            f"체결가: {event.get('filled_price_local')}\n"
            f"cycle: {cycle_id or '-'}"
        )
        self.send_message(message)


_telegram_notifier: TelegramNotifier | None = None


def get_notification_service() -> TelegramNotifier:
    global _telegram_notifier
    if _telegram_notifier is None:
        _telegram_notifier = TelegramNotifier()
    return _telegram_notifier
