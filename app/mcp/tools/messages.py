"""Message-related MCP tools."""

import json
from typing import Any

from telethon import TelegramClient
from telethon.tl.types import Message


def _format_message(msg: Message) -> dict[str, Any]:
    """Format a message for JSON output.

    Args:
        msg: The Telegram message

    Returns:
        Dict with message data
    """
    result: dict[str, Any] = {
        "id": msg.id,
        "date": msg.date.isoformat() if msg.date else None,
        "text": msg.text,
    }

    # Sender info
    if msg.sender:
        sender = msg.sender
        result["sender"] = {
            "id": sender.id,
            "first_name": getattr(sender, "first_name", None),
            "last_name": getattr(sender, "last_name", None),
            "username": getattr(sender, "username", None),
        }

    # Reply info
    if msg.reply_to:
        result["reply_to_message_id"] = msg.reply_to.reply_to_msg_id

    # Media type (don't include actual media data)
    if msg.media:
        media_type = type(msg.media).__name__
        result["has_media"] = True
        result["media_type"] = media_type
    else:
        result["has_media"] = False

    # Forward info
    if msg.forward:
        result["is_forwarded"] = True
    else:
        result["is_forwarded"] = False

    return result


async def get_messages(
    client: TelegramClient,
    chat_id: int | str,
    limit: int = 20,
) -> str:
    """Get messages from a Telegram chat.

    Args:
        client: The user's Telegram client
        chat_id: The chat ID or username
        limit: Maximum number of messages to return

    Returns:
        JSON string with list of messages
    """
    entity = await client.get_entity(chat_id)
    messages = await client.get_messages(entity, limit=limit)

    formatted = [_format_message(msg) for msg in messages if isinstance(msg, Message)]

    return json.dumps({
        "messages": formatted,
        "count": len(formatted),
        "chat_id": entity.id,
    }, indent=2)


async def send_message(
    client: TelegramClient,
    chat_id: int | str,
    text: str,
) -> str:
    """Send a message to a Telegram chat.

    Args:
        client: The user's Telegram client
        chat_id: The chat ID or username
        text: The message text to send

    Returns:
        JSON string with sent message info
    """
    entity = await client.get_entity(chat_id)
    message = await client.send_message(entity, text)

    return json.dumps({
        "success": True,
        "message_id": message.id,
        "chat_id": entity.id,
        "date": message.date.isoformat() if message.date else None,
    }, indent=2)


async def search_messages(
    client: TelegramClient,
    query: str,
    chat_id: int | str | None = None,
    limit: int = 20,
) -> str:
    """Search for messages in a chat or globally.

    Args:
        client: The user's Telegram client
        query: Search query
        chat_id: Optional: limit search to specific chat
        limit: Maximum number of results

    Returns:
        JSON string with matching messages
    """
    entity = None
    if chat_id:
        entity = await client.get_entity(chat_id)

    messages = []
    async for msg in client.iter_messages(entity, search=query, limit=limit):
        if isinstance(msg, Message):
            formatted = _format_message(msg)
            # Add chat info for global searches
            if not chat_id and msg.chat:
                formatted["chat"] = {
                    "id": msg.chat.id,
                    "title": getattr(msg.chat, "title", None)
                    or getattr(msg.chat, "first_name", None),
                }
            messages.append(formatted)

    return json.dumps({
        "messages": messages,
        "count": len(messages),
        "query": query,
    }, indent=2)
