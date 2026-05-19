"""Encrypted session storage for Telegram sessions."""

from cryptography.fernet import Fernet
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.session import TelegramSession

settings = get_settings()


class SessionStore:
    """Manages encrypted storage of Telegram session strings.

    Uses Fernet symmetric encryption (AES-128-CBC with HMAC) for at-rest encryption.
    Session strings contain authentication data and must be protected.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._fernet = Fernet(settings.encryption_key.encode())

    def encrypt(self, session_string: str) -> bytes:
        """Encrypt a session string for storage."""
        return self._fernet.encrypt(session_string.encode())

    def decrypt(self, encrypted_data: bytes) -> str:
        """Decrypt a stored session string."""
        return self._fernet.decrypt(encrypted_data).decode()

    async def get_session(self, claude_user_id: str) -> TelegramSession | None:
        """Get an active session for a user.

        Returns None if no active session exists.
        """
        result = await self.db.execute(
            select(TelegramSession).where(
                TelegramSession.claude_user_id == claude_user_id,
                TelegramSession.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_any_session(self, claude_user_id: str) -> TelegramSession | None:
        """Get a session for a user, including inactive sessions."""
        result = await self.db.execute(
            select(TelegramSession).where(TelegramSession.claude_user_id == claude_user_id)
        )
        return result.scalar_one_or_none()

    async def get_session_string(self, claude_user_id: str) -> str | None:
        """Get the decrypted session string for a user.

        Returns None if no active session exists.
        """
        session = await self.get_session(claude_user_id)
        if session:
            return self.decrypt(session.session_data)
        return None

    async def save_session(
        self,
        claude_user_id: str,
        session_string: str,
        phone_hash: str,
    ) -> TelegramSession:
        """Save or update a session for a user.

        If a session already exists for the user, it will be replaced.
        """
        encrypted = self.encrypt(session_string)

        # Check for any existing session, including inactive rows. claude_user_id is
        # unique, so reconnecting after a soft-delete must update/reactivate it.
        existing = await self.get_any_session(claude_user_id)
        if existing:
            existing.session_data = encrypted
            existing.phone_hash = phone_hash
            existing.is_active = True
            await self.db.commit()
            return existing

        session = TelegramSession(
            claude_user_id=claude_user_id,
            phone_hash=phone_hash,
            session_data=encrypted,
        )
        self.db.add(session)
        await self.db.commit()
        return session

    async def delete_session(self, claude_user_id: str) -> bool:
        """Soft-delete a session by marking it inactive.

        Returns True if a session was deactivated, False if no session found.
        """
        result = await self.db.execute(
            update(TelegramSession)
            .where(
                TelegramSession.claude_user_id == claude_user_id,
                TelegramSession.is_active == True,
            )
            .values(is_active=False)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def update_last_used(self, claude_user_id: str) -> None:
        """Update the last_used_at timestamp for a session."""
        from datetime import datetime

        await self.db.execute(
            update(TelegramSession)
            .where(TelegramSession.claude_user_id == claude_user_id)
            .values(last_used_at=datetime.utcnow())
        )
        await self.db.commit()
