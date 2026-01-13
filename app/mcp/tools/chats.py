"""Chat and contact-related MCP tools."""

import json
from typing import Any

from telethon import TelegramClient
from telethon.tl.types import (
    Channel,
    Chat,
    User,
    InputPeerChannel,
    InputPeerChat,
    InputPeerUser,
)


async def list_chats(client: TelegramClient, limit: int = 20) -> str:
    """List all Telegram chats (dialogs) for the user.

    Args:
        client: The user's Telegram client
        limit: Maximum number of chats to return

    Returns:
        JSON string with list of chats
    """
    dialogs = await client.get_dialogs(limit=limit)

    chats = []
    for dialog in dialogs:
        entity = dialog.entity
        chat_info = {
            "id": dialog.id,
            "name": dialog.name,
            "unread_count": dialog.unread_count,
        }

        # Add type-specific info
        if isinstance(entity, User):
            chat_info["type"] = "private"
            chat_info["username"] = entity.username
            chat_info["is_bot"] = entity.bot
        elif isinstance(entity, Chat):
            chat_info["type"] = "group"
            chat_info["participants_count"] = getattr(entity, "participants_count", None)
        elif isinstance(entity, Channel):
            chat_info["type"] = "channel" if entity.broadcast else "supergroup"
            chat_info["username"] = entity.username
            chat_info["participants_count"] = getattr(entity, "participants_count", None)

        # Last message preview (truncated for privacy)
        if dialog.message:
            text = dialog.message.text or ""
            chat_info["last_message"] = {
                "text": text[:100] + "..." if len(text) > 100 else text,
                "date": dialog.message.date.isoformat() if dialog.message.date else None,
            }

        chats.append(chat_info)

    return json.dumps({"chats": chats, "count": len(chats)}, indent=2)


async def get_chat(client: TelegramClient, chat_id: int | str) -> str:
    """Get detailed information about a specific chat.

    Args:
        client: The user's Telegram client
        chat_id: The chat ID or username

    Returns:
        JSON string with chat details
    """
    entity = await client.get_entity(chat_id)

    chat_info: dict[str, Any] = {
        "id": entity.id,
    }

    if isinstance(entity, User):
        chat_info.update({
            "type": "private",
            "first_name": entity.first_name,
            "last_name": entity.last_name,
            "username": entity.username,
            "phone": "***" if entity.phone else None,  # Never expose actual phone
            "is_bot": entity.bot,
            "is_verified": entity.verified,
            "is_premium": getattr(entity, "premium", False),
        })
    elif isinstance(entity, Chat):
        chat_info.update({
            "type": "group",
            "title": entity.title,
            "participants_count": getattr(entity, "participants_count", None),
            "date": entity.date.isoformat() if entity.date else None,
        })
    elif isinstance(entity, Channel):
        chat_info.update({
            "type": "channel" if entity.broadcast else "supergroup",
            "title": entity.title,
            "username": entity.username,
            "participants_count": getattr(entity, "participants_count", None),
            "is_verified": entity.verified,
            "date": entity.date.isoformat() if entity.date else None,
        })

        # Get full channel info for more details
        try:
            full = await client.get_entity(entity)
            if hasattr(full, "about"):
                chat_info["about"] = full.about
        except Exception:
            pass

    return json.dumps(chat_info, indent=2)


async def list_contacts(client: TelegramClient) -> str:
    """List all contacts.

    Args:
        client: The user's Telegram client

    Returns:
        JSON string with list of contacts
    """
    result = await client.get_contacts()

    contacts = []
    for user in result:
        contacts.append({
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "is_mutual_contact": user.mutual_contact,
        })

    return json.dumps({"contacts": contacts, "count": len(contacts)}, indent=2)


async def search_contacts(client: TelegramClient, query: str) -> str:
    """Search for contacts by name or username.

    Args:
        client: The user's Telegram client
        query: Search query

    Returns:
        JSON string with matching contacts
    """
    result = await client.get_contacts()

    query_lower = query.lower()
    matches = []

    for user in result:
        # Search in name and username
        name = f"{user.first_name or ''} {user.last_name or ''}".lower()
        username = (user.username or "").lower()

        if query_lower in name or query_lower in username:
            matches.append({
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
            })

    return json.dumps({"contacts": matches, "count": len(matches)}, indent=2)


async def get_participants(
    client: TelegramClient,
    chat_id: int | str,
    limit: int = 100,
) -> str:
    """Get participants of a group or channel.

    Args:
        client: The user's Telegram client
        chat_id: The group/channel ID or username
        limit: Maximum number of participants to return

    Returns:
        JSON string with list of participants
    """
    entity = await client.get_entity(chat_id)

    participants = []
    async for user in client.iter_participants(entity, limit=limit):
        participants.append({
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "is_bot": user.bot,
        })

    return json.dumps({
        "participants": participants,
        "count": len(participants),
        "chat_id": entity.id,
    }, indent=2)
