"""Authentication middleware for MCP requests."""

import hashlib
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import verify_access_token
from app.database import async_session_maker
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


def hash_chat_id(chat_id: int | str) -> str:
    """Hash a chat ID for audit logging.

    We never store actual chat IDs in logs - only hashes for correlation.
    """
    return hashlib.sha256(str(chat_id).encode()).hexdigest()[:16]


async def validate_bearer_token(authorization: str | None) -> dict | None:
    """Validate a Bearer token and return the payload.

    Args:
        authorization: The Authorization header value

    Returns:
        Token payload dict if valid, None otherwise
    """
    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]  # Remove "Bearer " prefix
    return verify_access_token(token)


async def log_audit(
    claude_user_id: str,
    action: str,
    tool_name: str | None = None,
    chat_id: int | str | None = None,
    success: bool = True,
    error_code: str | None = None,
) -> None:
    """Log an audit entry for a user action.

    IMPORTANT: This only logs metadata, never message content.

    Args:
        claude_user_id: The user who performed the action
        action: The action type (e.g., "send_message", "list_chats")
        tool_name: The MCP tool name if applicable
        chat_id: The chat ID (will be hashed before storage)
        success: Whether the action succeeded
        error_code: Error code if action failed
    """
    async with async_session_maker() as db:
        audit = AuditLog(
            claude_user_id=claude_user_id,
            action=action,
            tool_name=tool_name,
            chat_id_hash=hash_chat_id(chat_id) if chat_id else None,
            timestamp=datetime.utcnow(),
            success=success,
            error_code=error_code,
        )
        db.add(audit)
        await db.commit()

    logger.debug(
        f"Audit: user={claude_user_id} action={action} tool={tool_name} success={success}"
    )
