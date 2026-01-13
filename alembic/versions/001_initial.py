"""Initial database schema

Revision ID: 001_initial
Revises:
Create Date: 2026-01-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Telegram sessions table
    op.create_table(
        "telegram_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("claude_user_id", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("phone_hash", sa.String(64), nullable=False),
        sa.Column("session_data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=True),
    )

    # OAuth clients table
    op.create_table(
        "oauth_clients",
        sa.Column("client_id", sa.String(36), primary_key=True),
        sa.Column("client_secret_hash", sa.String(128), nullable=False),
        sa.Column("redirect_uris", sa.Text(), nullable=False),
        sa.Column("client_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # OAuth authorization codes table
    op.create_table(
        "oauth_codes",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column(
            "client_id",
            sa.String(36),
            sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claude_user_id", sa.String(255), nullable=False),
        sa.Column("code_challenge", sa.String(128), nullable=False),
        sa.Column("code_challenge_method", sa.String(10), default="S256", nullable=True),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("scopes", sa.Text(), default="telegram:read telegram:write", nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), default=False, nullable=True),
    )

    # OAuth tokens table
    op.create_table(
        "oauth_tokens",
        sa.Column("token_id", sa.String(36), primary_key=True),
        sa.Column(
            "client_id",
            sa.String(36),
            sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claude_user_id", sa.String(255), nullable=False, index=True),
        sa.Column("access_token_hash", sa.String(64), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), default=False, nullable=True),
    )

    # Audit logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("claude_user_id", sa.String(255), nullable=False, index=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=True),
        sa.Column("chat_id_hash", sa.String(64), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("oauth_tokens")
    op.drop_table("oauth_codes")
    op.drop_table("oauth_clients")
    op.drop_table("telegram_sessions")
