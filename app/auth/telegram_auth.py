"""Telegram authentication flow - bridges OAuth with phone/SMS verification."""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession

from app.auth.tokens import generate_authorization_code
from app.config import get_settings
from app.database import get_db
from app.models.oauth import OAuthCode
from app.models.session import TelegramSession
from app.telegram.session_store import SessionStore

router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory="app/templates")

# In-memory store for pending auth flows (auth_state -> PendingAuth)
# In production, consider using Redis for multi-instance deployments
_pending_auths: dict[str, dict[str, Any]] = {}


def _hash_phone(phone: str) -> str:
    """Hash a phone number for secure storage."""
    return hashlib.sha256(phone.encode()).hexdigest()


@router.get("/phone", response_class=HTMLResponse)
async def phone_form(request: Request, oauth_state: str | None = None):
    """Display phone number entry form."""
    if not oauth_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing oauth_state parameter",
        )

    # Verify oauth_state matches session
    session_state = request.session.get("oauth_state")
    if session_state != oauth_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid oauth_state",
        )

    return templates.TemplateResponse(
        "phone.html",
        {"request": request, "oauth_state": oauth_state, "error": None},
    )


@router.post("/phone", response_class=HTMLResponse)
async def submit_phone(
    request: Request,
    phone: str = Form(...),
    oauth_state: str = Form(...),
):
    """Process phone number and send verification code."""
    # Verify oauth_state matches session
    session_state = request.session.get("oauth_state")
    if session_state != oauth_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid oauth_state",
        )

    # Normalize phone number
    phone = phone.strip().replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        phone = "+" + phone

    try:
        # Create temporary Telegram client
        client = TelegramClient(
            StringSession(),
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        await client.connect()

        # Send verification code
        sent_code = await client.send_code_request(phone)

        # Store pending auth state
        _pending_auths[oauth_state] = {
            "phone": phone,
            "phone_code_hash": sent_code.phone_code_hash,
            "client": client,
            "created_at": datetime.utcnow(),
        }

        # Redirect to code entry
        return RedirectResponse(
            url=f"/auth/code?oauth_state={oauth_state}",
            status_code=status.HTTP_302_FOUND,
        )

    except PhoneNumberInvalidError:
        return templates.TemplateResponse(
            "phone.html",
            {
                "request": request,
                "oauth_state": oauth_state,
                "error": "Invalid phone number. Please enter a valid number with country code.",
            },
        )
    except FloodWaitError as e:
        return templates.TemplateResponse(
            "phone.html",
            {
                "request": request,
                "oauth_state": oauth_state,
                "error": f"Too many attempts. Please try again in {e.seconds} seconds.",
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "phone.html",
            {
                "request": request,
                "oauth_state": oauth_state,
                "error": f"An error occurred: {str(e)}",
            },
        )


@router.get("/code", response_class=HTMLResponse)
async def code_form(request: Request, oauth_state: str | None = None):
    """Display SMS code entry form."""
    if not oauth_state or oauth_state not in _pending_auths:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired auth session",
        )

    return templates.TemplateResponse(
        "code.html",
        {"request": request, "oauth_state": oauth_state, "error": None},
    )


@router.post("/code", response_class=HTMLResponse)
async def submit_code(
    request: Request,
    code: str = Form(...),
    oauth_state: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Verify SMS code and complete authentication."""
    if oauth_state not in _pending_auths:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired auth session",
        )

    pending = _pending_auths[oauth_state]
    client: TelegramClient = pending["client"]
    phone = pending["phone"]
    phone_code_hash = pending["phone_code_hash"]

    # Clean up the code (remove spaces/dashes)
    code = code.strip().replace(" ", "").replace("-", "")

    try:
        # Attempt to sign in
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)

        # Success! Complete the auth flow
        return await _complete_auth(request, oauth_state, client, phone, db)

    except SessionPasswordNeededError:
        # 2FA is enabled, redirect to 2FA form
        return RedirectResponse(
            url=f"/auth/2fa?oauth_state={oauth_state}",
            status_code=status.HTTP_302_FOUND,
        )
    except PhoneCodeInvalidError:
        return templates.TemplateResponse(
            "code.html",
            {
                "request": request,
                "oauth_state": oauth_state,
                "error": "Invalid code. Please check and try again.",
            },
        )
    except PhoneCodeExpiredError:
        # Clean up
        del _pending_auths[oauth_state]
        await client.disconnect()
        return templates.TemplateResponse(
            "code.html",
            {
                "request": request,
                "oauth_state": oauth_state,
                "error": "Code expired. Please start over.",
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "code.html",
            {
                "request": request,
                "oauth_state": oauth_state,
                "error": f"An error occurred: {str(e)}",
            },
        )


@router.get("/2fa", response_class=HTMLResponse)
async def twofa_form(request: Request, oauth_state: str | None = None):
    """Display 2FA password entry form."""
    if not oauth_state or oauth_state not in _pending_auths:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired auth session",
        )

    return templates.TemplateResponse(
        "2fa.html",
        {"request": request, "oauth_state": oauth_state, "error": None},
    )


@router.post("/2fa", response_class=HTMLResponse)
async def submit_2fa(
    request: Request,
    password: str = Form(...),
    oauth_state: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Verify 2FA password and complete authentication."""
    if oauth_state not in _pending_auths:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired auth session",
        )

    pending = _pending_auths[oauth_state]
    client: TelegramClient = pending["client"]
    phone = pending["phone"]

    try:
        # Sign in with 2FA password
        await client.sign_in(password=password)

        # Success! Complete the auth flow
        return await _complete_auth(request, oauth_state, client, phone, db)

    except Exception as e:
        return templates.TemplateResponse(
            "2fa.html",
            {
                "request": request,
                "oauth_state": oauth_state,
                "error": f"Invalid password or error: {str(e)}",
            },
        )


async def _complete_auth(
    request: Request,
    oauth_state: str,
    client: TelegramClient,
    phone: str,
    db: AsyncSession,
) -> RedirectResponse:
    """Complete the authentication flow after successful Telegram sign-in."""
    # Get OAuth params from session
    oauth_params = request.session.get("oauth_params")
    if not oauth_params:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing OAuth parameters",
        )

    # Export session string
    session_string = client.session.save()

    # Generate a unique user ID (we use a hash of the session to ensure uniqueness)
    # In a real app, you might use the Telegram user ID
    me = await client.get_me()
    claude_user_id = f"tg_{me.id}"

    # Encrypt and store session
    session_store = SessionStore(db)
    encrypted_session = session_store.encrypt(session_string)

    # Create or update session record
    telegram_session = TelegramSession(
        claude_user_id=claude_user_id,
        phone_hash=_hash_phone(phone),
        session_data=encrypted_session,
    )
    db.add(telegram_session)

    # Generate authorization code
    auth_code = generate_authorization_code()
    oauth_code = OAuthCode(
        code=auth_code,
        client_id=oauth_params["client_id"],
        claude_user_id=claude_user_id,
        code_challenge=oauth_params["code_challenge"],
        code_challenge_method=oauth_params["code_challenge_method"],
        redirect_uri=oauth_params["redirect_uri"],
        scopes=oauth_params["scope"],
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(oauth_code)
    await db.commit()

    # Clean up pending auth
    del _pending_auths[oauth_state]
    # Don't disconnect the client - it's now stored for future use

    # Clear session
    request.session.clear()

    # Redirect back to Claude with authorization code
    redirect_uri = oauth_params["redirect_uri"]
    state = oauth_params["state"]
    return RedirectResponse(
        url=f"{redirect_uri}?code={auth_code}&state={state}",
        status_code=status.HTTP_302_FOUND,
    )
