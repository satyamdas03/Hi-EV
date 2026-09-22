"""Optional Telegram relay for Hi-EV proactive alerts.

This is a skeleton implementation. When EV_TELEGRAM_ENABLED is true and both
EV_TELEGRAM_BOT_TOKEN and EV_TELEGRAM_CHAT_ID are configured, urgent deadline
alerts and the morning brief are also forwarded to Telegram as a fallback
notification channel.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ev.config import get_settings

logger = logging.getLogger(__name__)


class TelegramRelay:
    """Send plain-text notifications to a configured Telegram chat."""

    def __init__(self):
        settings = get_settings()
        self.enabled = settings.telegram_enabled
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.token.get_secret_value()}/{method}"

    async def send(self, text: str, parse_mode: str | None = None) -> dict[str, Any]:
        """Send a text message to the configured chat if enabled."""
        if not self.enabled or not self.token or not self.chat_id:
            return {"sent": False, "reason": "not_configured"}

        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text[:4096],  # Telegram message limit
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(self._url("sendMessage"), json=payload)
                data = response.json()
                if not data.get("ok"):
                    logger.warning("Telegram API error: %s", data)
                    return {"sent": False, "error": data}
                return {"sent": True, "message_id": data["result"]["message_id"]}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram send failed: %s", exc)
            return {"sent": False, "error": str(exc)}

    async def alert(self, title: str, body: str, items: list[dict] | None = None) -> dict[str, Any]:
        """Format and send an alert notification."""
        lines = [f"🚨 *{title}*", "", body]
        if items:
            lines.extend(["", *["- " + (item.get("title") or str(item)) for item in items[:10]]])
        return await self.send("\n".join(lines), parse_mode="Markdown")

    async def morning_brief(self, text: str) -> dict[str, Any]:
        """Format and send the morning brief."""
        return await self.send(f"📋 *Morning brief*\n\n{text}", parse_mode="Markdown")
