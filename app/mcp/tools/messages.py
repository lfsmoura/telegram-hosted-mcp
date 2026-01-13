"""Message-related MCP tools."""

import json
from datetime import datetime
from typing import Any

from telethon import TelegramClient
from telethon.tl.types import (
    Message,
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageMediaWebPage,
    ReplyInlineMarkup,
    KeyboardButtonCallback,
    KeyboardButtonUrl,
    ReactionEmoji,
    ReactionCustomEmoji,
)
from telethon.tl.functions.messages import (
    SendReactionRequest,
)


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

    # Media type
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

    # Pinned
    result["is_pinned"] = getattr(msg, "pinned", False)

    # Reactions
    if msg.reactions and msg.reactions.results:
        reactions = []
        for r in msg.reactions.results:
            if isinstance(r.reaction, ReactionEmoji):
                reactions.append({
                    "emoji": r.reaction.emoticon,
                    "count": r.count,
                })
        result["reactions"] = reactions

    return result


async def get_messages(
    client: TelegramClient,
    chat_id: int | str,
    page: int = 1,
    page_size: int = 20,
) -> str:
    """Get paginated messages from a Telegram chat.

    Args:
        client: The user's Telegram client
        chat_id: The chat ID or username
        page: Page number (1-indexed)
        page_size: Number of messages per page

    Returns:
        JSON string with list of messages
    """
    entity = await client.get_entity(chat_id)
    offset = (page - 1) * page_size

    messages = await client.get_messages(entity, limit=page_size, add_offset=offset)

    formatted = [_format_message(msg) for msg in messages if isinstance(msg, Message)]

    return json.dumps({
        "messages": formatted,
        "page": page,
        "page_size": page_size,
        "count": len(formatted),
        "chat_id": entity.id,
    }, indent=2)


async def list_messages(
    client: TelegramClient,
    chat_id: int | str,
    limit: int = 20,
    search_query: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> str:
    """List messages with optional filtering.

    Args:
        client: The user's Telegram client
        chat_id: The chat ID or username
        limit: Maximum number of messages
        search_query: Optional search query
        from_date: Optional start date (ISO format)
        to_date: Optional end date (ISO format)

    Returns:
        JSON string with list of messages
    """
    entity = await client.get_entity(chat_id)

    # Parse dates if provided
    offset_date = None
    if to_date:
        offset_date = datetime.fromisoformat(to_date.replace("Z", "+00:00"))

    messages = []
    async for msg in client.iter_messages(
        entity,
        limit=limit,
        search=search_query,
        offset_date=offset_date,
    ):
        if isinstance(msg, Message):
            # Filter by from_date if specified
            if from_date:
                from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
                if msg.date and msg.date.replace(tzinfo=None) < from_dt.replace(tzinfo=None):
                    continue

            messages.append(_format_message(msg))

    return json.dumps({
        "messages": messages,
        "count": len(messages),
        "chat_id": entity.id,
    }, indent=2)


async def send_message(
    client: TelegramClient,
    chat_id: int | str,
    message: str,
) -> str:
    """Send a message to a Telegram chat.

    Args:
        client: The user's Telegram client
        chat_id: The chat ID or username
        message: The message text to send

    Returns:
        JSON string with sent message info
    """
    entity = await client.get_entity(chat_id)
    msg = await client.send_message(entity, message)

    return json.dumps({
        "success": True,
        "message_id": msg.id,
        "chat_id": entity.id,
        "date": msg.date.isoformat() if msg.date else None,
    }, indent=2)


async def reply_to_message(
    client: TelegramClient,
    chat_id: int | str,
    message_id: int,
    text: str,
) -> str:
    """Reply to a specific message.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        message_id: ID of message to reply to
        text: Reply text

    Returns:
        JSON string with sent message info
    """
    entity = await client.get_entity(chat_id)
    msg = await client.send_message(entity, text, reply_to=message_id)

    return json.dumps({
        "success": True,
        "message_id": msg.id,
        "reply_to_message_id": message_id,
        "chat_id": entity.id,
        "date": msg.date.isoformat() if msg.date else None,
    }, indent=2)


async def edit_message(
    client: TelegramClient,
    chat_id: int | str,
    message_id: int,
    new_text: str,
) -> str:
    """Edit a message.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        message_id: ID of message to edit
        new_text: New message text

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)
    await client.edit_message(entity, message_id, new_text)

    return json.dumps({
        "success": True,
        "message_id": message_id,
        "chat_id": entity.id,
        "edited": True,
    }, indent=2)


async def delete_message(
    client: TelegramClient,
    chat_id: int | str,
    message_id: int,
) -> str:
    """Delete a message.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        message_id: ID of message to delete

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)
    await client.delete_messages(entity, [message_id])

    return json.dumps({
        "success": True,
        "message_id": message_id,
        "chat_id": entity.id,
        "deleted": True,
    }, indent=2)


async def forward_message(
    client: TelegramClient,
    from_chat_id: int | str,
    message_id: int,
    to_chat_id: int | str,
) -> str:
    """Forward a message to another chat.

    Args:
        client: The user's Telegram client
        from_chat_id: Source chat ID or username
        message_id: ID of message to forward
        to_chat_id: Destination chat ID or username

    Returns:
        JSON string with result
    """
    from_entity = await client.get_entity(from_chat_id)
    to_entity = await client.get_entity(to_chat_id)

    result = await client.forward_messages(to_entity, message_id, from_entity)

    new_message_id = result[0].id if result else None

    return json.dumps({
        "success": True,
        "original_message_id": message_id,
        "new_message_id": new_message_id,
        "from_chat_id": from_entity.id,
        "to_chat_id": to_entity.id,
    }, indent=2)


async def pin_message(
    client: TelegramClient,
    chat_id: int | str,
    message_id: int,
) -> str:
    """Pin a message in a chat.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        message_id: ID of message to pin

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)
    await client.pin_message(entity, message_id)

    return json.dumps({
        "success": True,
        "message_id": message_id,
        "chat_id": entity.id,
        "pinned": True,
    }, indent=2)


async def unpin_message(
    client: TelegramClient,
    chat_id: int | str,
    message_id: int,
) -> str:
    """Unpin a message in a chat.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        message_id: ID of message to unpin

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)
    await client.unpin_message(entity, message_id)

    return json.dumps({
        "success": True,
        "message_id": message_id,
        "chat_id": entity.id,
        "unpinned": True,
    }, indent=2)


async def mark_as_read(client: TelegramClient, chat_id: int | str) -> str:
    """Mark all messages in a chat as read.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)
    await client.send_read_acknowledge(entity)

    return json.dumps({
        "success": True,
        "chat_id": entity.id,
        "marked_read": True,
    }, indent=2)


async def get_message_context(
    client: TelegramClient,
    chat_id: int | str,
    message_id: int,
    context_size: int = 5,
) -> str:
    """Get messages around a specific message for context.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        message_id: The message ID to get context for
        context_size: Number of messages before and after

    Returns:
        JSON string with context messages
    """
    entity = await client.get_entity(chat_id)

    # Get messages before
    messages_before = await client.get_messages(
        entity,
        limit=context_size,
        max_id=message_id,
    )

    # Get the target message and messages after
    messages_after = await client.get_messages(
        entity,
        limit=context_size + 1,
        min_id=message_id - 1,
    )

    all_messages = list(reversed(messages_before)) + list(messages_after)

    # Remove duplicates and sort by ID
    seen_ids = set()
    unique_messages = []
    for msg in all_messages:
        if isinstance(msg, Message) and msg.id not in seen_ids:
            seen_ids.add(msg.id)
            unique_messages.append(msg)

    unique_messages.sort(key=lambda m: m.id)
    formatted = [_format_message(msg) for msg in unique_messages]

    return json.dumps({
        "messages": formatted,
        "target_message_id": message_id,
        "count": len(formatted),
        "chat_id": entity.id,
    }, indent=2)


async def get_history(
    client: TelegramClient,
    chat_id: int | str,
    limit: int = 50,
) -> str:
    """Get chat history.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        limit: Maximum number of messages

    Returns:
        JSON string with chat history
    """
    entity = await client.get_entity(chat_id)
    messages = await client.get_messages(entity, limit=limit)

    formatted = [_format_message(msg) for msg in messages if isinstance(msg, Message)]

    return json.dumps({
        "messages": formatted,
        "count": len(formatted),
        "chat_id": entity.id,
    }, indent=2)


async def get_pinned_messages(client: TelegramClient, chat_id: int | str) -> str:
    """Get all pinned messages in a chat.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username

    Returns:
        JSON string with pinned messages
    """
    entity = await client.get_entity(chat_id)

    messages = []
    async for msg in client.iter_messages(entity, filter=None):
        if isinstance(msg, Message) and getattr(msg, "pinned", False):
            messages.append(_format_message(msg))
            if len(messages) >= 100:  # Limit
                break

    return json.dumps({
        "pinned_messages": messages,
        "count": len(messages),
        "chat_id": entity.id,
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


async def get_last_interaction(client: TelegramClient, contact_id: int | str) -> str:
    """Get the last interaction with a contact.

    Args:
        client: The user's Telegram client
        contact_id: Contact user ID or username

    Returns:
        JSON string with last interaction info
    """
    entity = await client.get_entity(contact_id)
    messages = await client.get_messages(entity, limit=1)

    if not messages:
        return json.dumps({
            "contact_id": entity.id,
            "last_interaction": None,
        }, indent=2)

    msg = messages[0]
    return json.dumps({
        "contact_id": entity.id,
        "last_interaction": _format_message(msg) if isinstance(msg, Message) else None,
    }, indent=2)


async def create_poll(
    client: TelegramClient,
    chat_id: int | str,
    question: str,
    options: list[str],
    multiple_choice: bool = False,
    quiz_mode: bool = False,
    public_votes: bool = False,
    close_date: str | None = None,
) -> str:
    """Create a poll in a chat.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        question: Poll question
        options: List of answer options
        multiple_choice: Allow multiple answers
        quiz_mode: Create a quiz with one correct answer
        public_votes: Show who voted for what
        close_date: Optional close date (ISO format)

    Returns:
        JSON string with created poll info
    """
    from telethon.tl.types import Poll, PollAnswer
    from telethon.tl.functions.messages import SendMediaRequest
    from telethon.tl.types import InputMediaPoll

    entity = await client.get_entity(chat_id)

    # Create poll answers
    poll_answers = [
        PollAnswer(text=opt, option=bytes([i]))
        for i, opt in enumerate(options)
    ]

    poll = Poll(
        id=0,
        question=question,
        answers=poll_answers,
        multiple_choice=multiple_choice,
        quiz=quiz_mode,
        public_voters=public_votes,
    )

    # Parse close date if provided
    close_period = None
    if close_date:
        close_dt = datetime.fromisoformat(close_date.replace("Z", "+00:00"))
        close_period = int((close_dt - datetime.utcnow()).total_seconds())

    result = await client.send_message(
        entity,
        file=InputMediaPoll(
            poll=poll,
            close_period=close_period,
        ),
    )

    return json.dumps({
        "success": True,
        "message_id": result.id,
        "chat_id": entity.id,
        "question": question,
        "options_count": len(options),
    }, indent=2)


async def list_inline_buttons(
    client: TelegramClient,
    chat_id: int | str,
    message_id: int,
    limit: int = 50,
) -> str:
    """List inline keyboard buttons on a message.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        message_id: Message ID with inline keyboard

    Returns:
        JSON string with button info
    """
    entity = await client.get_entity(chat_id)
    messages = await client.get_messages(entity, ids=message_id)

    if not messages or not isinstance(messages[0], Message):
        return json.dumps({"error": "Message not found"}, indent=2)

    msg = messages[0]
    if not msg.reply_markup or not isinstance(msg.reply_markup, ReplyInlineMarkup):
        return json.dumps({
            "buttons": [],
            "message_id": message_id,
            "has_inline_keyboard": False,
        }, indent=2)

    buttons = []
    for row_idx, row in enumerate(msg.reply_markup.rows):
        for btn_idx, button in enumerate(row.buttons):
            button_info = {
                "row": row_idx,
                "index": btn_idx,
                "text": button.text,
            }
            if isinstance(button, KeyboardButtonCallback):
                button_info["type"] = "callback"
                button_info["data"] = button.data.decode("utf-8", errors="ignore")
            elif isinstance(button, KeyboardButtonUrl):
                button_info["type"] = "url"
                button_info["url"] = button.url
            else:
                button_info["type"] = type(button).__name__

            buttons.append(button_info)

    return json.dumps({
        "buttons": buttons,
        "message_id": message_id,
        "has_inline_keyboard": True,
        "button_count": len(buttons),
    }, indent=2)


async def press_inline_button(
    client: TelegramClient,
    chat_id: int | str,
    message_id: int,
    button_text: str | None = None,
    button_index: int | None = None,
) -> str:
    """Press an inline keyboard button.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        message_id: Message ID with inline keyboard
        button_text: Button text to match (optional)
        button_index: Button index to press (optional)

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)
    messages = await client.get_messages(entity, ids=message_id)

    if not messages or not isinstance(messages[0], Message):
        return json.dumps({"error": "Message not found"}, indent=2)

    msg = messages[0]
    if not msg.reply_markup or not isinstance(msg.reply_markup, ReplyInlineMarkup):
        return json.dumps({"error": "No inline keyboard found"}, indent=2)

    # Find the button
    target_button = None
    current_index = 0
    for row in msg.reply_markup.rows:
        for button in row.buttons:
            if button_text and button.text == button_text:
                target_button = button
                break
            if button_index is not None and current_index == button_index:
                target_button = button
                break
            current_index += 1
        if target_button:
            break

    if not target_button:
        return json.dumps({"error": "Button not found"}, indent=2)

    if not isinstance(target_button, KeyboardButtonCallback):
        return json.dumps({"error": "Button is not a callback button"}, indent=2)

    # Press the button
    result = await msg.click(data=target_button.data)

    return json.dumps({
        "success": True,
        "button_pressed": target_button.text,
        "message_id": message_id,
        "chat_id": entity.id,
    }, indent=2)


async def send_reaction(
    client: TelegramClient,
    chat_id: int | str,
    message_id: int,
    emoji: str,
    big: bool = False,
) -> str:
    """Add a reaction to a message.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        message_id: Message ID
        emoji: Reaction emoji
        big: Whether to send a big reaction animation

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)

    await client(SendReactionRequest(
        peer=entity,
        msg_id=message_id,
        reaction=[ReactionEmoji(emoticon=emoji)],
        big=big,
    ))

    return json.dumps({
        "success": True,
        "message_id": message_id,
        "chat_id": entity.id,
        "reaction": emoji,
    }, indent=2)


async def remove_reaction(
    client: TelegramClient,
    chat_id: int | str,
    message_id: int,
) -> str:
    """Remove reaction from a message.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        message_id: Message ID

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)

    await client(SendReactionRequest(
        peer=entity,
        msg_id=message_id,
        reaction=[],
    ))

    return json.dumps({
        "success": True,
        "message_id": message_id,
        "chat_id": entity.id,
        "reaction_removed": True,
    }, indent=2)


async def get_message_reactions(
    client: TelegramClient,
    chat_id: int | str,
    message_id: int,
    limit: int = 50,
) -> str:
    """Get all reactions on a message.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        message_id: Message ID
        limit: Maximum number of reactors to return per reaction

    Returns:
        JSON string with reactions
    """
    entity = await client.get_entity(chat_id)
    messages = await client.get_messages(entity, ids=message_id)

    if not messages or not isinstance(messages[0], Message):
        return json.dumps({"error": "Message not found"}, indent=2)

    msg = messages[0]

    if not msg.reactions or not msg.reactions.results:
        return json.dumps({
            "reactions": [],
            "message_id": message_id,
            "total_count": 0,
        }, indent=2)

    reactions = []
    for r in msg.reactions.results:
        reaction_info = {
            "count": r.count,
        }
        if isinstance(r.reaction, ReactionEmoji):
            reaction_info["emoji"] = r.reaction.emoticon
        elif isinstance(r.reaction, ReactionCustomEmoji):
            reaction_info["custom_emoji_id"] = r.reaction.document_id

        reactions.append(reaction_info)

    return json.dumps({
        "reactions": reactions,
        "message_id": message_id,
        "total_count": sum(r["count"] for r in reactions),
    }, indent=2)


async def get_media_info(
    client: TelegramClient,
    chat_id: int | str,
    message_id: int,
) -> str:
    """Get media information from a message.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        message_id: Message ID

    Returns:
        JSON string with media info
    """
    entity = await client.get_entity(chat_id)
    messages = await client.get_messages(entity, ids=message_id)

    if not messages or not isinstance(messages[0], Message):
        return json.dumps({"error": "Message not found"}, indent=2)

    msg = messages[0]

    if not msg.media:
        return json.dumps({
            "has_media": False,
            "message_id": message_id,
        }, indent=2)

    media_info: dict[str, Any] = {
        "has_media": True,
        "message_id": message_id,
        "media_type": type(msg.media).__name__,
    }

    if isinstance(msg.media, MessageMediaPhoto):
        media_info["type"] = "photo"
    elif isinstance(msg.media, MessageMediaDocument):
        media_info["type"] = "document"
        doc = msg.media.document
        if doc:
            media_info["file_name"] = getattr(doc, "file_name", None)
            media_info["mime_type"] = doc.mime_type
            media_info["size"] = doc.size
    elif isinstance(msg.media, MessageMediaWebPage):
        media_info["type"] = "webpage"
        if msg.media.webpage and hasattr(msg.media.webpage, "url"):
            media_info["url"] = msg.media.webpage.url
            media_info["title"] = getattr(msg.media.webpage, "title", None)

    return json.dumps(media_info, indent=2)
