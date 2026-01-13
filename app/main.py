"""Main FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.auth.oauth import router as oauth_router
from app.auth.telegram_auth import router as telegram_auth_router
from app.config import get_settings
from app.database import init_db
from app.mcp.server import mcp_app
from app.telegram.client_pool import client_pool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Telegram MCP server...")
    await init_db()
    await client_pool.start()
    logger.info("Telegram MCP server started")

    yield

    # Shutdown
    logger.info("Shutting down Telegram MCP server...")
    await client_pool.stop()
    logger.info("Telegram MCP server stopped")


# Create main FastAPI app
app = FastAPI(
    title="Telegram MCP Server",
    description="Hosted Telegram MCP server for Claude Teams",
    version="1.0.0",
    lifespan=lifespan,
)

# Add session middleware for OAuth state management
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.jwt_secret,
    session_cookie="telegram_mcp_session",
    max_age=3600,  # 1 hour
    same_site="lax",
    https_only=settings.base_url.startswith("https"),
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://claude.ai", "https://claude.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include OAuth routes
app.include_router(oauth_router, tags=["OAuth"])

# Include Telegram auth routes
app.include_router(telegram_auth_router, prefix="/auth", tags=["Telegram Auth"])

# Mount MCP server
app.mount("/mcp", mcp_app)


@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "name": "Telegram MCP Server",
        "version": "1.0.0",
        "mcp_endpoint": f"{settings.base_url}/mcp",
        "oauth_metadata": f"{settings.base_url}/.well-known/oauth-authorization-server",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "active_telegram_clients": client_pool.active_clients,
    }


@app.get("/me")
async def get_me(request: Request):
    """Get current user's connection status.

    Requires Bearer token authentication.
    """
    from app.mcp.middleware import validate_bearer_token
    from app.database import async_session_maker
    from app.telegram.session_store import SessionStore

    auth_header = request.headers.get("Authorization")
    payload = await validate_bearer_token(auth_header)

    if not payload:
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid or missing Bearer token"},
        )

    claude_user_id = payload["sub"]

    # Check if user has an active session
    async with async_session_maker() as db:
        session_store = SessionStore(db)
        session = await session_store.get_session(claude_user_id)

        if not session:
            return {"connected": False}

        # Try to get Telegram user info
        try:
            client = await client_pool.get_client(claude_user_id, db)
            me = await client.get_me()
            return {
                "connected": True,
                "telegram_user": {
                    "id": me.id,
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "username": me.username,
                },
            }
        except Exception:
            return {
                "connected": True,
                "telegram_user": None,
                "note": "Could not fetch Telegram user info",
            }


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )
