"""Draft message MCP tools."""

import json
from typing import Any

from telethon import TelegramClient
from telethon.tl.functions.messages import (
    SaveDraftRequest,
    GetAllDraftsRequest,
    ClearAllDraftsRequest,
)
from telethon.tl.types import (
    DraftMessage,
    UpdateDraftMessage,
)


async def save_draft(
    client: TelegramClient,
    chat_id: int | str,
    message: str,
    reply_to_msg_id: int | None = None,
    no_webpage: bool = False,
) -> str:
    """Save a draft message for a chat.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        message: Draft message text
        reply_to_msg_id: Optional message ID to reply to
        no_webpage: Don't generate link previews

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)

    await client(SaveDraftRequest(
        peer=entity,
        message=message,
        reply_to_msg_id=reply_to_msg_id,
        no_webpage=no_webpage,
    ))

    return json.dumps({
        "success": True,
        "chat_id": entity.id,
        "draft_saved": True,
        "message_length": len(message),
    }, indent=2)


async def get_drafts(client: TelegramClient) -> str:
    """Get all draft messages.

    Args:
        client: The user's Telegram client

    Returns:
        JSON string with all drafts
    """
    result = await client(GetAllDraftsRequest())

    drafts = []
    for update in result.updates:
        if isinstance(update, UpdateDraftMessage):
            draft = update.draft
            if isinstance(draft, DraftMessage):
                draft_info: dict[str, Any] = {
                    "message": draft.message,
                    "date": draft.date.isoformat() if draft.date else None,
                    "no_webpage": draft.no_webpage,
                }

                if draft.reply_to:
                    draft_info["reply_to_msg_id"] = getattr(
                        draft.reply_to, "reply_to_msg_id", None
                    )

                # Get peer info
                peer = update.peer
                if hasattr(peer, "user_id"):
                    draft_info["peer_type"] = "user"
                    draft_info["peer_id"] = peer.user_id
                elif hasattr(peer, "chat_id"):
                    draft_info["peer_type"] = "chat"
                    draft_info["peer_id"] = peer.chat_id
                elif hasattr(peer, "channel_id"):
                    draft_info["peer_type"] = "channel"
                    draft_info["peer_id"] = peer.channel_id

                drafts.append(draft_info)

    return json.dumps({
        "drafts": drafts,
        "count": len(drafts),
    }, indent=2)


async def clear_draft(client: TelegramClient, chat_id: int | str) -> str:
    """Clear draft message for a specific chat.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)

    # Save empty message to clear draft
    await client(SaveDraftRequest(
        peer=entity,
        message="",
    ))

    return json.dumps({
        "success": True,
        "chat_id": entity.id,
        "draft_cleared": True,
    }, indent=2)


async def clear_all_drafts(client: TelegramClient) -> str:
    """Clear all draft messages.

    Args:
        client: The user's Telegram client

    Returns:
        JSON string with result
    """
    await client(ClearAllDraftsRequest())

    return json.dumps({
        "success": True,
        "all_drafts_cleared": True,
    }, indent=2)
