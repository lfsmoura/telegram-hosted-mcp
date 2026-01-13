"""Telegram session model for encrypted session storage."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TelegramSession(Base):
    """Encrypted Telegram session storage.

    Each Claude user can have at most one Telegram account connected.
    Sessions persist until explicitly revoked by the user.
    """

    __tablename__ = "telegram_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    claude_user_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone_hash: Mapped[str] = mapped_column(String(64))  # SHA-256 hash of phone number
    session_data: Mapped[bytes] = mapped_column(LargeBinary)  # Fernet-encrypted session string
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
