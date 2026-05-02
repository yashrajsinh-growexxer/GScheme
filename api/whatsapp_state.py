from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict


SESSION_TTL = timedelta(hours=12)


@dataclass
class WhatsAppSession:
    user_id: str
    state: str = "menu"
    language_code: str = "en-IN"
    profile: Dict[str, str] = field(default_factory=dict)
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def reset(self) -> None:
        self.state = "menu"
        self.profile.clear()
        self.touch()


class WhatsAppStateManager:
    """Simple in-memory session store for WhatsApp conversations."""

    def __init__(self) -> None:
        self._sessions: Dict[str, WhatsAppSession] = {}

    def get_session(self, user_id: str) -> WhatsAppSession:
        self._prune_expired()
        session = self._sessions.get(user_id)
        if session is None:
            session = WhatsAppSession(user_id=user_id)
            self._sessions[user_id] = session
        session.touch()
        return session

    def reset_session(self, user_id: str) -> WhatsAppSession:
        session = self.get_session(user_id)
        session.reset()
        return session

    def _prune_expired(self) -> None:
        cutoff = datetime.now(timezone.utc) - SESSION_TTL
        expired = [
            user_id
            for user_id, session in self._sessions.items()
            if session.updated_at < cutoff
        ]
        for user_id in expired:
            self._sessions.pop(user_id, None)
