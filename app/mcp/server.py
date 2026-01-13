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
from app.mcp.tools import chats, messages, contacts, users, privacy, drafts


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
        # =====================
        # Chat & Group Management
        # =====================
        {
            "name": "get_chats",
            "description": "Get paginated list of Telegram chats",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer", "description": "Page number (1-indexed)", "default": 1},
                    "page_size": {"type": "integer", "description": "Number of chats per page", "default": 20},
                },
            },
        },
        {
            "name": "list_chats",
            "description": "List all Telegram chats with optional filtering by type",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_type": {"type": "string", "description": "Filter by type: private, group, supergroup, channel"},
                    "limit": {"type": "integer", "description": "Maximum number of chats to return", "default": 20},
                },
            },
        },
        {
            "name": "get_chat",
            "description": "Get detailed information about a specific chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "The chat ID or username"},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "create_group",
            "description": "Create a new group chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Group title"},
                    "user_ids": {"type": "array", "items": {"type": ["integer", "string"]}, "description": "List of user IDs/usernames to add"},
                },
                "required": ["title", "user_ids"],
            },
        },
        {
            "name": "invite_to_group",
            "description": "Invite users to a group or channel",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "group_id": {"type": ["integer", "string"], "description": "Group/channel ID or username"},
                    "user_ids": {"type": "array", "items": {"type": ["integer", "string"]}, "description": "List of user IDs/usernames to invite"},
                },
                "required": ["group_id", "user_ids"],
            },
        },
        {
            "name": "create_channel",
            "description": "Create a new channel or supergroup",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Channel title"},
                    "about": {"type": "string", "description": "Channel description", "default": ""},
                    "megagroup": {"type": "boolean", "description": "Create supergroup instead of channel", "default": False},
                },
                "required": ["title"],
            },
        },
        {
            "name": "edit_chat_title",
            "description": "Edit chat/channel title",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "title": {"type": "string", "description": "New title"},
                },
                "required": ["chat_id", "title"],
            },
        },
        {
            "name": "leave_chat",
            "description": "Leave a group or channel",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "get_participants",
            "description": "Get participants of a group or channel",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "limit": {"type": "integer", "description": "Maximum participants to return", "default": 100},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "get_admins",
            "description": "Get administrators of a group or channel",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "get_banned_users",
            "description": "Get banned users of a group or channel",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "promote_admin",
            "description": "Promote a user to admin",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "user_id": {"type": ["integer", "string"], "description": "User ID or username to promote"},
                },
                "required": ["chat_id", "user_id"],
            },
        },
        {
            "name": "demote_admin",
            "description": "Demote an admin",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "user_id": {"type": ["integer", "string"], "description": "User ID or username to demote"},
                },
                "required": ["chat_id", "user_id"],
            },
        },
        {
            "name": "ban_user",
            "description": "Ban a user from a group or channel",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "user_id": {"type": ["integer", "string"], "description": "User ID or username to ban"},
                },
                "required": ["chat_id", "user_id"],
            },
        },
        {
            "name": "unban_user",
            "description": "Unban a user from a group or channel",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "user_id": {"type": ["integer", "string"], "description": "User ID or username to unban"},
                },
                "required": ["chat_id", "user_id"],
            },
        },
        {
            "name": "get_invite_link",
            "description": "Get the invite link for a group or channel",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "export_chat_invite",
            "description": "Export a new invite link for a group or channel",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "import_chat_invite",
            "description": "Join a chat using an invite hash",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "hash": {"type": "string", "description": "Invite link hash (the part after t.me/+)"},
                },
                "required": ["hash"],
            },
        },
        {
            "name": "join_chat_by_link",
            "description": "Join a chat using a full invite link",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "link": {"type": "string", "description": "Full invite link (e.g., https://t.me/+abc123)"},
                },
                "required": ["link"],
            },
        },
        {
            "name": "subscribe_public_channel",
            "description": "Subscribe to a public channel",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel username"},
                },
                "required": ["channel"],
            },
        },
        {
            "name": "get_recent_actions",
            "description": "Get recent admin actions in a group or channel",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "limit": {"type": "integer", "description": "Maximum actions to return", "default": 50},
                },
                "required": ["chat_id"],
            },
        },
        # =====================
        # Messaging
        # =====================
        {
            "name": "get_messages",
            "description": "Get paginated messages from a chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "page": {"type": "integer", "description": "Page number", "default": 1},
                    "page_size": {"type": "integer", "description": "Messages per page", "default": 20},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "list_messages",
            "description": "List messages with optional search and date filtering",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "limit": {"type": "integer", "description": "Maximum messages", "default": 20},
                    "search_query": {"type": "string", "description": "Optional search query"},
                    "from_date": {"type": "string", "description": "Optional start date (ISO format)"},
                    "to_date": {"type": "string", "description": "Optional end date (ISO format)"},
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
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "message": {"type": "string", "description": "Message text to send"},
                },
                "required": ["chat_id", "message"],
            },
        },
        {
            "name": "reply_to_message",
            "description": "Reply to a specific message",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "message_id": {"type": "integer", "description": "Message ID to reply to"},
                    "text": {"type": "string", "description": "Reply text"},
                },
                "required": ["chat_id", "message_id", "text"],
            },
        },
        {
            "name": "edit_message",
            "description": "Edit a message",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "message_id": {"type": "integer", "description": "Message ID to edit"},
                    "new_text": {"type": "string", "description": "New message text"},
                },
                "required": ["chat_id", "message_id", "new_text"],
            },
        },
        {
            "name": "delete_message",
            "description": "Delete a message",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "message_id": {"type": "integer", "description": "Message ID to delete"},
                },
                "required": ["chat_id", "message_id"],
            },
        },
        {
            "name": "forward_message",
            "description": "Forward a message to another chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "from_chat_id": {"type": ["integer", "string"], "description": "Source chat ID or username"},
                    "message_id": {"type": "integer", "description": "Message ID to forward"},
                    "to_chat_id": {"type": ["integer", "string"], "description": "Destination chat ID or username"},
                },
                "required": ["from_chat_id", "message_id", "to_chat_id"],
            },
        },
        {
            "name": "pin_message",
            "description": "Pin a message in a chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "message_id": {"type": "integer", "description": "Message ID to pin"},
                },
                "required": ["chat_id", "message_id"],
            },
        },
        {
            "name": "unpin_message",
            "description": "Unpin a message in a chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "message_id": {"type": "integer", "description": "Message ID to unpin"},
                },
                "required": ["chat_id", "message_id"],
            },
        },
        {
            "name": "mark_as_read",
            "description": "Mark all messages in a chat as read",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "get_message_context",
            "description": "Get messages around a specific message for context",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "message_id": {"type": "integer", "description": "Target message ID"},
                    "context_size": {"type": "integer", "description": "Messages before and after", "default": 5},
                },
                "required": ["chat_id", "message_id"],
            },
        },
        {
            "name": "get_history",
            "description": "Get chat history",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "limit": {"type": "integer", "description": "Maximum messages", "default": 50},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "get_pinned_messages",
            "description": "Get all pinned messages in a chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "search_messages",
            "description": "Search for messages in a chat or globally",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "chat_id": {"type": ["integer", "string"], "description": "Optional: limit to specific chat"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 20},
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_last_interaction",
            "description": "Get the last interaction with a contact",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": ["integer", "string"], "description": "Contact user ID or username"},
                },
                "required": ["contact_id"],
            },
        },
        {
            "name": "create_poll",
            "description": "Create a poll in a chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "question": {"type": "string", "description": "Poll question"},
                    "options": {"type": "array", "items": {"type": "string"}, "description": "Answer options"},
                    "multiple_choice": {"type": "boolean", "description": "Allow multiple answers", "default": False},
                    "quiz_mode": {"type": "boolean", "description": "Create a quiz", "default": False},
                    "public_votes": {"type": "boolean", "description": "Show who voted", "default": False},
                    "close_date": {"type": "string", "description": "Optional close date (ISO format)"},
                },
                "required": ["chat_id", "question", "options"],
            },
        },
        {
            "name": "list_inline_buttons",
            "description": "List inline keyboard buttons on a message",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "message_id": {"type": "integer", "description": "Message ID with inline keyboard"},
                },
                "required": ["chat_id", "message_id"],
            },
        },
        {
            "name": "press_inline_button",
            "description": "Press an inline keyboard button",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "message_id": {"type": "integer", "description": "Message ID with inline keyboard"},
                    "button_text": {"type": "string", "description": "Button text to match (optional)"},
                    "button_index": {"type": "integer", "description": "Button index to press (optional)"},
                },
                "required": ["chat_id", "message_id"],
            },
        },
        {
            "name": "send_reaction",
            "description": "Add a reaction to a message",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "message_id": {"type": "integer", "description": "Message ID"},
                    "emoji": {"type": "string", "description": "Reaction emoji"},
                    "big": {"type": "boolean", "description": "Big reaction animation", "default": False},
                },
                "required": ["chat_id", "message_id", "emoji"],
            },
        },
        {
            "name": "remove_reaction",
            "description": "Remove reaction from a message",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "message_id": {"type": "integer", "description": "Message ID"},
                },
                "required": ["chat_id", "message_id"],
            },
        },
        {
            "name": "get_message_reactions",
            "description": "Get all reactions on a message",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "message_id": {"type": "integer", "description": "Message ID"},
                },
                "required": ["chat_id", "message_id"],
            },
        },
        {
            "name": "get_media_info",
            "description": "Get media information from a message",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "message_id": {"type": "integer", "description": "Message ID"},
                },
                "required": ["chat_id", "message_id"],
            },
        },
        # =====================
        # Contact Management
        # =====================
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
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "add_contact",
            "description": "Add a new contact",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Phone number (international format)"},
                    "first_name": {"type": "string", "description": "First name"},
                    "last_name": {"type": "string", "description": "Last name", "default": ""},
                },
                "required": ["phone", "first_name"],
            },
        },
        {
            "name": "delete_contact",
            "description": "Delete a contact",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": ["integer", "string"], "description": "User ID or username"},
                },
                "required": ["user_id"],
            },
        },
        {
            "name": "block_user",
            "description": "Block a user",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": ["integer", "string"], "description": "User ID or username"},
                },
                "required": ["user_id"],
            },
        },
        {
            "name": "unblock_user",
            "description": "Unblock a user",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": ["integer", "string"], "description": "User ID or username"},
                },
                "required": ["user_id"],
            },
        },
        {
            "name": "import_contacts",
            "description": "Import multiple contacts",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "contacts": {"type": "array", "items": {"type": "object"}, "description": "List of contacts with phone, first_name, last_name"},
                },
                "required": ["contacts"],
            },
        },
        {
            "name": "export_contacts",
            "description": "Export all contacts",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "get_blocked_users",
            "description": "Get list of blocked users",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "get_contact_ids",
            "description": "Get list of all contact IDs",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "get_direct_chat_by_contact",
            "description": "Find direct chat with a contact",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "contact_query": {"type": "string", "description": "Contact name or username"},
                },
                "required": ["contact_query"],
            },
        },
        {
            "name": "get_contact_chats",
            "description": "Get all chats involving a specific contact",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": ["integer", "string"], "description": "Contact user ID or username"},
                },
                "required": ["contact_id"],
            },
        },
        # =====================
        # User & Profile
        # =====================
        {
            "name": "get_me",
            "description": "Get current user's account information",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "update_profile",
            "description": "Update current user's profile",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "first_name": {"type": "string", "description": "New first name"},
                    "last_name": {"type": "string", "description": "New last name"},
                    "about": {"type": "string", "description": "New bio/about text"},
                },
            },
        },
        {
            "name": "delete_profile_photo",
            "description": "Delete current profile photo",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "get_user_photos",
            "description": "Get a user's profile photos",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": ["integer", "string"], "description": "User ID or username"},
                    "limit": {"type": "integer", "description": "Maximum photos", "default": 10},
                },
                "required": ["user_id"],
            },
        },
        {
            "name": "get_user_status",
            "description": "Get a user's online status",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": ["integer", "string"], "description": "User ID or username"},
                },
                "required": ["user_id"],
            },
        },
        # =====================
        # Search & Discovery
        # =====================
        {
            "name": "search_public_chats",
            "description": "Search for public chats/channels",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "resolve_username",
            "description": "Resolve a username to get user/channel ID",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Username to resolve"},
                },
                "required": ["username"],
            },
        },
        {
            "name": "get_sticker_sets",
            "description": "Get user's saved sticker sets",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "get_bot_info",
            "description": "Get information about a bot",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "bot_username": {"type": "string", "description": "Bot username"},
                },
                "required": ["bot_username"],
            },
        },
        # =====================
        # Privacy & Settings
        # =====================
        {
            "name": "get_privacy_settings",
            "description": "Get current privacy settings",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "set_privacy_settings",
            "description": "Set privacy settings for a specific key",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Privacy key (status, chat_invite, phone_call, phone_number, profile_photo, forwards, birthday)"},
                    "allow_users": {"type": "array", "items": {"type": ["integer", "string"]}, "description": "Users to allow"},
                    "disallow_users": {"type": "array", "items": {"type": ["integer", "string"]}, "description": "Users to disallow"},
                },
                "required": ["key"],
            },
        },
        {
            "name": "mute_chat",
            "description": "Mute notifications for a chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "unmute_chat",
            "description": "Unmute notifications for a chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "archive_chat",
            "description": "Archive a chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                },
                "required": ["chat_id"],
            },
        },
        {
            "name": "unarchive_chat",
            "description": "Unarchive a chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                },
                "required": ["chat_id"],
            },
        },
        # =====================
        # Drafts
        # =====================
        {
            "name": "save_draft",
            "description": "Save a draft message for a chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
                    "message": {"type": "string", "description": "Draft message text"},
                    "reply_to_msg_id": {"type": "integer", "description": "Optional message ID to reply to"},
                    "no_webpage": {"type": "boolean", "description": "Don't generate link previews", "default": False},
                },
                "required": ["chat_id", "message"],
            },
        },
        {
            "name": "get_drafts",
            "description": "Get all draft messages",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "clear_draft",
            "description": "Clear draft message for a specific chat",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"], "description": "Chat ID or username"},
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
        # Chat & Group Management
        if tool_name == "get_chats":
            result = await chats.get_chats(
                client,
                arguments.get("page", 1),
                arguments.get("page_size", 20),
            )
        elif tool_name == "list_chats":
            result = await chats.list_chats(
                client,
                arguments.get("chat_type"),
                arguments.get("limit", 20),
            )
        elif tool_name == "get_chat":
            result = await chats.get_chat(client, arguments["chat_id"])
        elif tool_name == "create_group":
            result = await chats.create_group(
                client,
                arguments["title"],
                arguments["user_ids"],
            )
        elif tool_name == "invite_to_group":
            result = await chats.invite_to_group(
                client,
                arguments["group_id"],
                arguments["user_ids"],
            )
        elif tool_name == "create_channel":
            result = await chats.create_channel(
                client,
                arguments["title"],
                arguments.get("about", ""),
                arguments.get("megagroup", False),
            )
        elif tool_name == "edit_chat_title":
            result = await chats.edit_chat_title(
                client,
                arguments["chat_id"],
                arguments["title"],
            )
        elif tool_name == "leave_chat":
            result = await chats.leave_chat(client, arguments["chat_id"])
        elif tool_name == "get_participants":
            result = await chats.get_participants(
                client,
                arguments["chat_id"],
                arguments.get("limit", 100),
            )
        elif tool_name == "get_admins":
            result = await chats.get_admins(client, arguments["chat_id"])
        elif tool_name == "get_banned_users":
            result = await chats.get_banned_users(client, arguments["chat_id"])
        elif tool_name == "promote_admin":
            result = await chats.promote_admin(
                client,
                arguments["chat_id"],
                arguments["user_id"],
            )
        elif tool_name == "demote_admin":
            result = await chats.demote_admin(
                client,
                arguments["chat_id"],
                arguments["user_id"],
            )
        elif tool_name == "ban_user":
            result = await chats.ban_user(
                client,
                arguments["chat_id"],
                arguments["user_id"],
            )
        elif tool_name == "unban_user":
            result = await chats.unban_user(
                client,
                arguments["chat_id"],
                arguments["user_id"],
            )
        elif tool_name == "get_invite_link":
            result = await chats.get_invite_link(client, arguments["chat_id"])
        elif tool_name == "export_chat_invite":
            result = await chats.export_chat_invite(client, arguments["chat_id"])
        elif tool_name == "import_chat_invite":
            result = await chats.import_chat_invite(client, arguments["hash"])
        elif tool_name == "join_chat_by_link":
            result = await chats.join_chat_by_link(client, arguments["link"])
        elif tool_name == "subscribe_public_channel":
            result = await chats.subscribe_public_channel(client, arguments["channel"])
        elif tool_name == "get_recent_actions":
            result = await chats.get_recent_actions(
                client,
                arguments["chat_id"],
                arguments.get("limit", 50),
            )

        # Messaging
        elif tool_name == "get_messages":
            result = await messages.get_messages(
                client,
                arguments["chat_id"],
                arguments.get("page", 1),
                arguments.get("page_size", 20),
            )
        elif tool_name == "list_messages":
            result = await messages.list_messages(
                client,
                arguments["chat_id"],
                arguments.get("limit", 20),
                arguments.get("search_query"),
                arguments.get("from_date"),
                arguments.get("to_date"),
            )
        elif tool_name == "send_message":
            result = await messages.send_message(
                client,
                arguments["chat_id"],
                arguments["message"],
            )
        elif tool_name == "reply_to_message":
            result = await messages.reply_to_message(
                client,
                arguments["chat_id"],
                arguments["message_id"],
                arguments["text"],
            )
        elif tool_name == "edit_message":
            result = await messages.edit_message(
                client,
                arguments["chat_id"],
                arguments["message_id"],
                arguments["new_text"],
            )
        elif tool_name == "delete_message":
            result = await messages.delete_message(
                client,
                arguments["chat_id"],
                arguments["message_id"],
            )
        elif tool_name == "forward_message":
            result = await messages.forward_message(
                client,
                arguments["from_chat_id"],
                arguments["message_id"],
                arguments["to_chat_id"],
            )
        elif tool_name == "pin_message":
            result = await messages.pin_message(
                client,
                arguments["chat_id"],
                arguments["message_id"],
            )
        elif tool_name == "unpin_message":
            result = await messages.unpin_message(
                client,
                arguments["chat_id"],
                arguments["message_id"],
            )
        elif tool_name == "mark_as_read":
            result = await messages.mark_as_read(client, arguments["chat_id"])
        elif tool_name == "get_message_context":
            result = await messages.get_message_context(
                client,
                arguments["chat_id"],
                arguments["message_id"],
                arguments.get("context_size", 5),
            )
        elif tool_name == "get_history":
            result = await messages.get_history(
                client,
                arguments["chat_id"],
                arguments.get("limit", 50),
            )
        elif tool_name == "get_pinned_messages":
            result = await messages.get_pinned_messages(client, arguments["chat_id"])
        elif tool_name == "search_messages":
            result = await messages.search_messages(
                client,
                arguments["query"],
                arguments.get("chat_id"),
                arguments.get("limit", 20),
            )
        elif tool_name == "get_last_interaction":
            result = await messages.get_last_interaction(client, arguments["contact_id"])
        elif tool_name == "create_poll":
            result = await messages.create_poll(
                client,
                arguments["chat_id"],
                arguments["question"],
                arguments["options"],
                arguments.get("multiple_choice", False),
                arguments.get("quiz_mode", False),
                arguments.get("public_votes", False),
                arguments.get("close_date"),
            )
        elif tool_name == "list_inline_buttons":
            result = await messages.list_inline_buttons(
                client,
                arguments["chat_id"],
                arguments["message_id"],
            )
        elif tool_name == "press_inline_button":
            result = await messages.press_inline_button(
                client,
                arguments["chat_id"],
                arguments["message_id"],
                arguments.get("button_text"),
                arguments.get("button_index"),
            )
        elif tool_name == "send_reaction":
            result = await messages.send_reaction(
                client,
                arguments["chat_id"],
                arguments["message_id"],
                arguments["emoji"],
                arguments.get("big", False),
            )
        elif tool_name == "remove_reaction":
            result = await messages.remove_reaction(
                client,
                arguments["chat_id"],
                arguments["message_id"],
            )
        elif tool_name == "get_message_reactions":
            result = await messages.get_message_reactions(
                client,
                arguments["chat_id"],
                arguments["message_id"],
            )
        elif tool_name == "get_media_info":
            result = await messages.get_media_info(
                client,
                arguments["chat_id"],
                arguments["message_id"],
            )

        # Contact Management
        elif tool_name == "list_contacts":
            result = await contacts.list_contacts(client)
        elif tool_name == "search_contacts":
            result = await contacts.search_contacts(client, arguments["query"])
        elif tool_name == "add_contact":
            result = await contacts.add_contact(
                client,
                arguments["phone"],
                arguments["first_name"],
                arguments.get("last_name", ""),
            )
        elif tool_name == "delete_contact":
            result = await contacts.delete_contact(client, arguments["user_id"])
        elif tool_name == "block_user":
            result = await contacts.block_user(client, arguments["user_id"])
        elif tool_name == "unblock_user":
            result = await contacts.unblock_user(client, arguments["user_id"])
        elif tool_name == "import_contacts":
            result = await contacts.import_contacts(client, arguments["contacts"])
        elif tool_name == "export_contacts":
            result = await contacts.export_contacts(client)
        elif tool_name == "get_blocked_users":
            result = await contacts.get_blocked_users(client)
        elif tool_name == "get_contact_ids":
            result = await contacts.get_contact_ids(client)
        elif tool_name == "get_direct_chat_by_contact":
            result = await contacts.get_direct_chat_by_contact(client, arguments["contact_query"])
        elif tool_name == "get_contact_chats":
            result = await contacts.get_contact_chats(client, arguments["contact_id"])

        # User & Profile
        elif tool_name == "get_me":
            result = await users.get_me(client)
        elif tool_name == "update_profile":
            result = await users.update_profile(
                client,
                arguments.get("first_name"),
                arguments.get("last_name"),
                arguments.get("about"),
            )
        elif tool_name == "delete_profile_photo":
            result = await users.delete_profile_photo(client)
        elif tool_name == "get_user_photos":
            result = await users.get_user_photos(
                client,
                arguments["user_id"],
                arguments.get("limit", 10),
            )
        elif tool_name == "get_user_status":
            result = await users.get_user_status(client, arguments["user_id"])

        # Search & Discovery
        elif tool_name == "search_public_chats":
            result = await users.search_public_chats(client, arguments["query"])
        elif tool_name == "resolve_username":
            result = await users.resolve_username(client, arguments["username"])
        elif tool_name == "get_sticker_sets":
            result = await users.get_sticker_sets(client)
        elif tool_name == "get_bot_info":
            result = await users.get_bot_info(client, arguments["bot_username"])

        # Privacy & Settings
        elif tool_name == "get_privacy_settings":
            result = await privacy.get_privacy_settings(client)
        elif tool_name == "set_privacy_settings":
            result = await privacy.set_privacy_settings(
                client,
                arguments["key"],
                arguments.get("allow_users"),
                arguments.get("disallow_users"),
            )
        elif tool_name == "mute_chat":
            result = await privacy.mute_chat(client, arguments["chat_id"])
        elif tool_name == "unmute_chat":
            result = await privacy.unmute_chat(client, arguments["chat_id"])
        elif tool_name == "archive_chat":
            result = await privacy.archive_chat(client, arguments["chat_id"])
        elif tool_name == "unarchive_chat":
            result = await privacy.unarchive_chat(client, arguments["chat_id"])

        # Drafts
        elif tool_name == "save_draft":
            result = await drafts.save_draft(
                client,
                arguments["chat_id"],
                arguments["message"],
                arguments.get("reply_to_msg_id"),
                arguments.get("no_webpage", False),
            )
        elif tool_name == "get_drafts":
            result = await drafts.get_drafts(client)
        elif tool_name == "clear_draft":
            result = await drafts.clear_draft(client, arguments["chat_id"])

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


async def handle_mcp_request_direct(request: Request) -> JSONResponse:
    """Handle MCP JSON-RPC requests directly (for use in main app)."""
    # Validate authentication
    auth_header = request.headers.get("Authorization")
    payload = await validate_bearer_token(auth_header)

    if not payload:
        return JSONResponse(
            status_code=401,
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32001, "message": "Invalid or missing Bearer token"},
                "id": None,
            },
        )

    claude_user_id = payload["sub"]

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

    except NoSessionError:
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
    except SessionExpiredError:
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


# Create the MCP FastAPI app (kept for backwards compatibility)
mcp_app = create_mcp_app()
