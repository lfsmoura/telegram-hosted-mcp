"""MCP server with Streamable HTTP transport."""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.database import async_session_maker
from app.mcp.middleware import log_audit, validate_bearer_token
from app.telegram.client_pool import NoSessionError, SessionExpiredError, client_pool

logger = logging.getLogger(__name__)

# Import tools
from app.mcp.tools import chats, messages


async def get_user_context(request: Request) -> dict:
    """Extract user context from Bearer token.

    Returns dict with claude_user_id and scopes.
    """
    auth_header = request.headers.get("Authorization")
    payload = await validate_bearer_token(auth_header)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "claude_user_id": payload["sub"],
        "scopes": payload.get("scopes", []),
    }


def create_mcp_app() -> FastAPI:
    """Create the FastAPI app for the MCP server."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage MCP server lifecycle."""
        await client_pool.start()
        yield
        await client_pool.stop()

    app = FastAPI(
        title="Telegram MCP Server",
        description="MCP server for Telegram integration",
        lifespan=lifespan,
    )

    @app.post("/")
    async def handle_mcp_request(request: Request):
        """Handle MCP JSON-RPC requests over HTTP."""
        # Validate authentication
        user_context = await get_user_context(request)
        claude_user_id = user_context["claude_user_id"]

        # Parse JSON-RPC request
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Parse error"},
                    "id": None,
                },
            )

        method = body.get("method", "")
        params = body.get("params", {})
        request_id = body.get("id")

        try:
            # Handle different MCP methods
            if method == "initialize":
                result = await handle_initialize(params)
            elif method == "tools/list":
                result = await handle_tools_list()
            elif method == "tools/call":
                result = await handle_tool_call(claude_user_id, params)
            else:
                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                        "id": request_id,
                    }
                )

            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id,
                }
            )

        except NoSessionError as e:
            await log_audit(claude_user_id, "error", error_code="no_session", success=False)
            return JSONResponse(
                status_code=401,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32001,
                        "message": "Telegram session not found. Please reconnect your account.",
                    },
                    "id": request_id,
                },
            )
        except SessionExpiredError as e:
            await log_audit(claude_user_id, "error", error_code="session_expired", success=False)
            return JSONResponse(
                status_code=401,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32002,
                        "message": "Telegram session expired. Please reconnect your account.",
                    },
                    "id": request_id,
                },
            )
        except Exception as e:
            logger.exception(f"Error handling MCP request: {e}")
            await log_audit(claude_user_id, "error", error_code=type(e).__name__, success=False)
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": str(e)},
                    "id": request_id,
                }
            )

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy", "active_clients": client_pool.active_clients}

    return app


async def handle_initialize(params: dict) -> dict:
    """Handle MCP initialize request."""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {},
        },
        "serverInfo": {
            "name": "telegram-mcp",
            "version": "1.0.0",
        },
    }


async def handle_tools_list() -> dict:
    """Handle MCP tools/list request."""
    tools = [
        # Messages (P0)
        {
            "name": "list_chats",
            "description": "List all Telegram chats (dialogs) for the user",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of chats to return",
                        "default": 20,
                    },
                },
            },
        },
        {
            "name": "get_chat",
            "description": "Get detailed information about a specific chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": ["integer", "string"],
                        "description": "The chat ID or username",
                    },
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "get_messages",
            "description": "Get messages from a Telegram chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": ["integer", "string"],
                        "description": "The chat ID or username",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of messages to return",
                        "default": 20,
                    },
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "send_message",
            "description": "Send a message to a Telegram chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": ["integer", "string"],
                        "description": "The chat ID or username",
                    },
                    "text": {
                        "type": "string",
                        "description": "The message text to send",
                    },
                },
                "required": ["chat_id", "text"],
            },
        },
        {
            "name": "search_messages",
            "description": "Search for messages in a chat or globally",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "chat_id": {
                        "type": ["integer", "string"],
                        "description": "Optional: limit search to specific chat",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        },
        # Contacts (P1)
        {
            "name": "list_contacts",
            "description": "List all contacts",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "search_contacts",
            "description": "Search for contacts by name or username",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                },
                "required": ["query"],
            },
        },
        # Groups (P1)
        {
            "name": "get_participants",
            "description": "Get participants of a group or channel",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": ["integer", "string"],
                        "description": "The group/channel ID or username",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of participants to return",
                        "default": 100,
                    },
                },
                "required": ["chat_id"],
            },
        },
    ]

    return {"tools": tools}


async def handle_tool_call(claude_user_id: str, params: dict) -> dict:
    """Handle MCP tools/call request."""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    if not tool_name:
        raise ValueError("Missing tool name")

    # Get database session
    async with async_session_maker() as db:
        # Get user's Telegram client
        client = await client_pool.get_client(claude_user_id, db)

        # Route to appropriate tool handler
        if tool_name == "list_chats":
            result = await chats.list_chats(client, arguments.get("limit", 20))
        elif tool_name == "get_chat":
            result = await chats.get_chat(client, arguments["chat_id"])
        elif tool_name == "get_messages":
            result = await messages.get_messages(
                client,
                arguments["chat_id"],
                arguments.get("limit", 20),
            )
        elif tool_name == "send_message":
            result = await messages.send_message(
                client,
                arguments["chat_id"],
                arguments["text"],
            )
        elif tool_name == "search_messages":
            result = await messages.search_messages(
                client,
                arguments["query"],
                arguments.get("chat_id"),
                arguments.get("limit", 20),
            )
        elif tool_name == "list_contacts":
            result = await chats.list_contacts(client)
        elif tool_name == "search_contacts":
            result = await chats.search_contacts(client, arguments["query"])
        elif tool_name == "get_participants":
            result = await chats.get_participants(
                client,
                arguments["chat_id"],
                arguments.get("limit", 100),
            )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

        # Log audit (success)
        chat_id = arguments.get("chat_id")
        await log_audit(
            claude_user_id,
            action=tool_name,
            tool_name=tool_name,
            chat_id=chat_id,
            success=True,
        )

        return {"content": [{"type": "text", "text": result}]}


# Create the MCP FastAPI app
mcp_app = create_mcp_app()
