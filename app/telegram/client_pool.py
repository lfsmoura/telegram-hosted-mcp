"""Multi-tenant Telegram client pool manager."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.sessions import StringSession

from app.config import get_settings
from app.telegram.session_store import SessionStore

settings = get_settings()
logger = logging.getLogger(__name__)


class NoSessionError(Exception):
    """Raised when no session exists for a user."""

    pass


class SessionExpiredError(Exception):
    """Raised when a Telegram session has been revoked or expired."""

    pass


class ClientPool:
    """Manages Telethon client instances for multiple users.

    Features:
    - Per-user client caching with LRU eviction
    - Automatic idle client cleanup
    - Thread-safe client access via per-user locks
    - Graceful shutdown of all clients
    """

    def __init__(self, max_clients: int = 100, max_idle_seconds: int = 300):
        """Initialize the client pool.

        Args:
            max_clients: Maximum number of concurrent clients to keep in memory
            max_idle_seconds: Disconnect clients idle longer than this
        """
        self._clients: dict[str, TelegramClient] = {}
        self._last_used: dict[str, datetime] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        self._max_clients = max_clients
        self._max_idle_seconds = max_idle_seconds
        self._cleanup_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the client pool background tasks."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Client pool started")

    async def stop(self) -> None:
        """Stop the client pool and disconnect all clients."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Disconnect all clients
        for user_id, client in list(self._clients.items()):
            try:
                await client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting client for {user_id}: {e}")

        self._clients.clear()
        self._last_used.clear()
        logger.info("Client pool stopped")

    async def get_client(
        self,
        claude_user_id: str,
        db: AsyncSession,
    ) -> TelegramClient:
        """Get or create a connected Telegram client for a user.

        Args:
            claude_user_id: The user's ID from OAuth
            db: Database session for loading stored sessions

        Returns:
            Connected TelegramClient instance

        Raises:
            NoSessionError: If no stored session exists for the user
            SessionExpiredError: If the stored session has been revoked
        """
        # Get or create lock for this user
        async with self._global_lock:
            if claude_user_id not in self._locks:
                self._locks[claude_user_id] = asyncio.Lock()
            lock = self._locks[claude_user_id]

        async with lock:
            # Check if we have a cached client
            if claude_user_id in self._clients:
                client = self._clients[claude_user_id]
                if client.is_connected():
                    self._last_used[claude_user_id] = datetime.utcnow()
                    return client
                else:
                    # Client disconnected, remove from cache
                    del self._clients[claude_user_id]
                    if claude_user_id in self._last_used:
                        del self._last_used[claude_user_id]

            # Need to create new client - first check capacity
            async with self._global_lock:
                if len(self._clients) >= self._max_clients:
                    await self._evict_oldest()

            # Load session from database
            session_store = SessionStore(db)
            session_string = await session_store.get_session_string(claude_user_id)

            if not session_string:
                raise NoSessionError(f"No Telegram session found for user {claude_user_id}")

            # Create and connect client
            client = TelegramClient(
                StringSession(session_string),
                settings.telegram_api_id,
                settings.telegram_api_hash,
            )

            try:
                await client.connect()

                # Verify the session is still valid
                if not await client.is_user_authorized():
                    await client.disconnect()
                    raise SessionExpiredError(
                        f"Telegram session expired for user {claude_user_id}"
                    )

            except Exception as e:
                await client.disconnect()
                raise

            # Cache the client
            self._clients[claude_user_id] = client
            self._last_used[claude_user_id] = datetime.utcnow()

            # Update last_used in database
            await session_store.update_last_used(claude_user_id)

            logger.info(f"Created new Telegram client for user {claude_user_id}")
            return client

    async def revoke_session(
        self,
        claude_user_id: str,
        db: AsyncSession,
        logout: bool = True,
    ) -> None:
        """Revoke a user's session and disconnect their client.

        Args:
            claude_user_id: The user's ID
            db: Database session
            logout: If True, also log out from Telegram (invalidates session server-side)
        """
        async with self._global_lock:
            if claude_user_id in self._locks:
                lock = self._locks[claude_user_id]
            else:
                lock = asyncio.Lock()

        async with lock:
            # Disconnect and remove cached client
            if claude_user_id in self._clients:
                client = self._clients.pop(claude_user_id)
                if logout:
                    try:
                        await client.log_out()
                    except Exception as e:
                        logger.warning(f"Error logging out client: {e}")
                await client.disconnect()

                if claude_user_id in self._last_used:
                    del self._last_used[claude_user_id]

            # Delete session from database
            session_store = SessionStore(db)
            await session_store.delete_session(claude_user_id)

        logger.info(f"Revoked session for user {claude_user_id}")

    async def _evict_oldest(self) -> None:
        """Evict the least recently used client to make room."""
        if not self._last_used:
            return

        # Find oldest
        oldest_user = min(self._last_used.keys(), key=lambda k: self._last_used[k])

        if oldest_user in self._clients:
            client = self._clients.pop(oldest_user)
            try:
                await client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting evicted client: {e}")
            del self._last_used[oldest_user]
            logger.debug(f"Evicted client for user {oldest_user}")

    async def _cleanup_loop(self) -> None:
        """Background task to clean up idle clients."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_idle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_idle(self) -> None:
        """Disconnect clients that have been idle too long."""
        now = datetime.utcnow()
        to_evict = []

        for user_id, last_used in list(self._last_used.items()):
            idle_seconds = (now - last_used).total_seconds()
            if idle_seconds > self._max_idle_seconds:
                to_evict.append(user_id)

        for user_id in to_evict:
            async with self._global_lock:
                if user_id in self._clients:
                    client = self._clients.pop(user_id)
                    try:
                        await client.disconnect()
                    except Exception as e:
                        logger.warning(f"Error disconnecting idle client: {e}")
                    if user_id in self._last_used:
                        del self._last_used[user_id]
                    logger.debug(f"Cleaned up idle client for user {user_id}")

    @property
    def active_clients(self) -> int:
        """Number of currently cached clients."""
        return len(self._clients)


# Global client pool instance
client_pool = ClientPool()
