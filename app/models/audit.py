"""Audit log model for metadata-only logging."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """Metadata-only audit log.

    IMPORTANT: Never log message content, actual chat IDs, phone numbers, or contact names.
    Only log hashed identifiers and action metadata for security auditing.
    """

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    claude_user_id: Mapped[str] = mapped_column(String(255), index=True)
    action: Mapped[str] = mapped_column(String(64))  # e.g., "send_message", "get_chats"
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chat_id_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256 hash
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    success: Mapped[bool] = mapped_column(Boolean)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
