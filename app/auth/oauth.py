"""OAuth 2.0 endpoints for Claude Teams integration."""

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import (
    create_access_token,
    create_refresh_token,
    generate_authorization_code,
    generate_client_secret,
    hash_token,
    verify_refresh_token,
)
from app.config import get_settings
from app.database import get_db
from app.models.oauth import OAuthClient, OAuthCode, OAuthToken

router = APIRouter()
settings = get_settings()


def hash_client_secret(secret: str) -> str:
    """Hash a client secret using SHA-256.

    Client secrets are already high-entropy random strings,
    so we don't need bcrypt's slow hashing.
    """
    return hashlib.sha256(secret.encode()).hexdigest()


def verify_client_secret(secret: str, hashed: str) -> bool:
    """Verify a client secret against its hash."""
    return secrets.compare_digest(hash_client_secret(secret), hashed)


class ClientRegistrationRequest(BaseModel):
    """Request body for dynamic client registration."""

    redirect_uris: list[str]
    client_name: str | None = None


class ClientRegistrationResponse(BaseModel):
    """Response for dynamic client registration."""

    client_id: str
    client_secret: str
    redirect_uris: list[str]
    client_name: str | None = None


class TokenResponse(BaseModel):
    """OAuth token response."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str | None = None
    scope: str


@router.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    """OAuth 2.0 Authorization Server Metadata (RFC 8414)."""
    return {
        "issuer": settings.base_url,
        "authorization_endpoint": f"{settings.base_url}/oauth/authorize",
        "token_endpoint": f"{settings.base_url}/oauth/token",
        "registration_endpoint": f"{settings.base_url}/oauth/register",
        "revocation_endpoint": f"{settings.base_url}/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
        "scopes_supported": ["telegram:read", "telegram:write", "telegram:admin"],
    }


@router.post("/oauth/register", response_model=ClientRegistrationResponse)
async def register_client(
    request: ClientRegistrationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Dynamic Client Registration (RFC 7591)."""
    client_id = secrets.token_urlsafe(16)
    client_secret = generate_client_secret()

    client = OAuthClient(
        client_id=client_id,
        client_secret_hash=hash_client_secret(client_secret),
        redirect_uris=json.dumps(request.redirect_uris),
        client_name=request.client_name,
    )
    db.add(client)
    await db.commit()

    return ClientRegistrationResponse(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uris=request.redirect_uris,
        client_name=request.client_name,
    )


@router.get("/oauth/authorize")
async def authorize(
    request: Request,
    response_type: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str,
    state: str,
    scope: str = "telegram:read telegram:write",
    db: AsyncSession = Depends(get_db),
):
    """Authorization endpoint - starts the Telegram auth flow."""
    # Validate response_type
    if response_type != "code":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only response_type=code is supported",
        )

    # Validate PKCE
    if code_challenge_method != "S256":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only S256 code_challenge_method is supported",
        )

    # Validate client
    result = await db.execute(
        select(OAuthClient).where(OAuthClient.client_id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client_id",
        )

    # Validate redirect_uri
    allowed_uris = json.loads(client.redirect_uris)
    if redirect_uri not in allowed_uris:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect_uri",
        )

    # Store auth request state in session and redirect to Telegram auth
    # We use a secure cookie to maintain state during the auth flow
    auth_state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = auth_state
    request.session["oauth_params"] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "state": state,
        "scope": scope,
    }

    # Redirect to Telegram phone entry
    return RedirectResponse(
        url=f"/auth/phone?oauth_state={auth_state}",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/oauth/token")
async def token_exchange(
    grant_type: str = Form(...),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    code_verifier: str | None = Form(None),
    refresh_token: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Token endpoint - exchange authorization code or refresh token."""
    # Validate client credentials
    result = await db.execute(
        select(OAuthClient).where(OAuthClient.client_id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client or not verify_client_secret(client_secret, client.client_secret_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
        )

    if grant_type == "authorization_code":
        return await _handle_authorization_code_grant(
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            client_id=client_id,
            db=db,
        )
    elif grant_type == "refresh_token":
        return await _handle_refresh_token_grant(
            refresh_token=refresh_token,
            client_id=client_id,
            db=db,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported grant_type",
        )


async def _handle_authorization_code_grant(
    code: str | None,
    redirect_uri: str | None,
    code_verifier: str | None,
    client_id: str,
    db: AsyncSession,
) -> TokenResponse:
    """Handle authorization code grant."""
    if not code or not redirect_uri or not code_verifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required parameters",
        )

    # Look up authorization code
    result = await db.execute(
        select(OAuthCode).where(
            OAuthCode.code == code,
            OAuthCode.client_id == client_id,
            OAuthCode.used == False,
        )
    )
    oauth_code = result.scalar_one_or_none()

    if not oauth_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authorization code",
        )

    # Check expiry
    if datetime.utcnow() > oauth_code.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code expired",
        )

    # Validate redirect_uri matches
    if oauth_code.redirect_uri != redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="redirect_uri mismatch",
        )

    # Verify PKCE code_verifier
    verifier_hash = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")

    if verifier_hash != oauth_code.code_challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code_verifier",
        )

    # Mark code as used
    oauth_code.used = True
    await db.commit()

    # Generate tokens
    scopes = oauth_code.scopes.split()
    access_token = create_access_token(oauth_code.claude_user_id, scopes)
    refresh_token = create_refresh_token(oauth_code.claude_user_id)

    # Store token record
    token_record = OAuthToken(
        client_id=client_id,
        claude_user_id=oauth_code.claude_user_id,
        access_token_hash=hash_token(access_token),
        refresh_token_hash=hash_token(refresh_token),
        scopes=oauth_code.scopes,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes),
    )
    db.add(token_record)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_expire_minutes * 60,
        refresh_token=refresh_token,
        scope=oauth_code.scopes,
    )


async def _handle_refresh_token_grant(
    refresh_token: str | None,
    client_id: str,
    db: AsyncSession,
) -> TokenResponse:
    """Handle refresh token grant."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing refresh_token",
        )

    # Verify refresh token
    payload = verify_refresh_token(refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token",
        )

    claude_user_id = payload["sub"]

    # Find existing token record
    refresh_hash = hash_token(refresh_token)
    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.refresh_token_hash == refresh_hash,
            OAuthToken.client_id == client_id,
            OAuthToken.revoked == False,
        )
    )
    token_record = result.scalar_one_or_none()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token",
        )

    # Generate new tokens
    scopes = token_record.scopes.split()
    new_access_token = create_access_token(claude_user_id, scopes)
    new_refresh_token = create_refresh_token(claude_user_id)

    # Update token record
    token_record.access_token_hash = hash_token(new_access_token)
    token_record.refresh_token_hash = hash_token(new_refresh_token)
    token_record.expires_at = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    await db.commit()

    return TokenResponse(
        access_token=new_access_token,
        expires_in=settings.jwt_expire_minutes * 60,
        refresh_token=new_refresh_token,
        scope=token_record.scopes,
    )


@router.post("/oauth/revoke")
async def revoke_token(
    token: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an access or refresh token."""
    # Validate client credentials
    result = await db.execute(
        select(OAuthClient).where(OAuthClient.client_id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client or not verify_client_secret(client_secret, client.client_secret_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
        )

    # Find and revoke token
    token_hash = hash_token(token)
    result = await db.execute(
        select(OAuthToken).where(
            (OAuthToken.access_token_hash == token_hash)
            | (OAuthToken.refresh_token_hash == token_hash),
            OAuthToken.client_id == client_id,
        )
    )
    token_record = result.scalar_one_or_none()

    if token_record:
        token_record.revoked = True
        await db.commit()

    # Always return success per RFC 7009
    return JSONResponse(content={}, status_code=status.HTTP_200_OK)
