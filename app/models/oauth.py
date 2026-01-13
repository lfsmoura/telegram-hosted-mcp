"""OAuth 2.0 models for client registration, authorization codes, and tokens."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OAuthClient(Base):
    """Registered OAuth clients (for dynamic client registration)."""

    __tablename__ = "oauth_clients"

    client_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    client_secret_hash: Mapped[str] = mapped_column(String(128))
    redirect_uris: Mapped[str] = mapped_column(Text)  # JSON array of URIs
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OAuthCode(Base):
    """Short-lived authorization codes with PKCE support."""

    __tablename__ = "oauth_codes"

    code: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    client_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("oauth_clients.client_id", ondelete="CASCADE")
    )
    claude_user_id: Mapped[str] = mapped_column(String(255))
    code_challenge: Mapped[str] = mapped_column(String(128))
    code_challenge_method: Mapped[str] = mapped_column(String(10), default="S256")
    redirect_uri: Mapped[str] = mapped_column(Text)
    scopes: Mapped[str] = mapped_column(Text, default="telegram:read telegram:write")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class OAuthToken(Base):
    """Issued access and refresh tokens."""

    __tablename__ = "oauth_tokens"

    token_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    client_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("oauth_clients.client_id", ondelete="CASCADE")
    )
    claude_user_id: Mapped[str] = mapped_column(String(255), index=True)
    access_token_hash: Mapped[str] = mapped_column(String(64))
    refresh_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scopes: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
