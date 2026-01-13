"""User and profile MCP tools."""

import json
from typing import Any

from telethon import TelegramClient
from telethon.tl.types import User, UserProfilePhoto
from telethon.tl.functions.account import (
    UpdateProfileRequest,
)
from telethon.tl.functions.photos import (
    DeletePhotosRequest,
    GetUserPhotosRequest,
)
from telethon.tl.functions.users import (
    GetFullUserRequest,
)


async def get_me(client: TelegramClient) -> str:
    """Get current user's account information.

    Args:
        client: The user's Telegram client

    Returns:
        JSON string with current user info
    """
    me = await client.get_me()

    return json.dumps({
        "id": me.id,
        "first_name": me.first_name,
        "last_name": me.last_name,
        "username": me.username,
        "phone": "***" if me.phone else None,  # Never expose actual phone
        "is_bot": me.bot,
        "is_verified": me.verified,
        "is_premium": getattr(me, "premium", False),
    }, indent=2)


async def update_profile(
    client: TelegramClient,
    first_name: str | None = None,
    last_name: str | None = None,
    about: str | None = None,
) -> str:
    """Update current user's profile.

    Args:
        client: The user's Telegram client
        first_name: New first name (optional)
        last_name: New last name (optional)
        about: New bio/about text (optional)

    Returns:
        JSON string with result
    """
    await client(UpdateProfileRequest(
        first_name=first_name or "",
        last_name=last_name or "",
        about=about or "",
    ))

    # Get updated info
    me = await client.get_me()

    return json.dumps({
        "success": True,
        "updated_profile": {
            "first_name": me.first_name,
            "last_name": me.last_name,
        }
    }, indent=2)


async def delete_profile_photo(client: TelegramClient) -> str:
    """Delete current profile photo.

    Args:
        client: The user's Telegram client

    Returns:
        JSON string with result
    """
    me = await client.get_me()

    if not me.photo:
        return json.dumps({
            "success": False,
            "error": "No profile photo to delete",
        }, indent=2)

    # Get the current photo to delete
    photos = await client(GetUserPhotosRequest(
        user_id=me,
        offset=0,
        max_id=0,
        limit=1,
    ))

    if photos.photos:
        await client(DeletePhotosRequest(id=[photos.photos[0]]))

    return json.dumps({
        "success": True,
        "deleted": True,
    }, indent=2)


async def get_user_photos(
    client: TelegramClient,
    user_id: int | str,
    limit: int = 10,
) -> str:
    """Get a user's profile photos.

    Args:
        client: The user's Telegram client
        user_id: User ID or username
        limit: Maximum number of photos to return

    Returns:
        JSON string with photo info
    """
    entity = await client.get_entity(user_id)

    if not isinstance(entity, User):
        return json.dumps({"error": "Not a user"}, indent=2)

    photos = await client(GetUserPhotosRequest(
        user_id=entity,
        offset=0,
        max_id=0,
        limit=limit,
    ))

    photo_list = []
    for photo in photos.photos:
        photo_info = {
            "id": photo.id,
            "date": photo.date.isoformat() if photo.date else None,
            "has_video": getattr(photo, "has_video", False),
        }
        photo_list.append(photo_info)

    return json.dumps({
        "user_id": entity.id,
        "photos": photo_list,
        "count": len(photo_list),
        "total": photos.count,
    }, indent=2)


async def get_user_status(client: TelegramClient, user_id: int | str) -> str:
    """Get a user's online status.

    Args:
        client: The user's Telegram client
        user_id: User ID or username

    Returns:
        JSON string with user status
    """
    entity = await client.get_entity(user_id)

    if not isinstance(entity, User):
        return json.dumps({"error": "Not a user"}, indent=2)

    status_type = type(entity.status).__name__ if entity.status else "Unknown"

    status_info: dict[str, Any] = {
        "user_id": entity.id,
        "first_name": entity.first_name,
        "last_name": entity.last_name,
        "username": entity.username,
        "status_type": status_type,
    }

    # Add more status details based on type
    if entity.status:
        if hasattr(entity.status, "was_online"):
            status_info["was_online"] = entity.status.was_online.isoformat()
        if hasattr(entity.status, "expires"):
            status_info["expires"] = entity.status.expires

        # Interpret status type
        if "Online" in status_type:
            status_info["is_online"] = True
        elif "Recently" in status_type:
            status_info["is_online"] = False
            status_info["last_seen"] = "recently"
        elif "Week" in status_type:
            status_info["is_online"] = False
            status_info["last_seen"] = "within week"
        elif "Month" in status_type:
            status_info["is_online"] = False
            status_info["last_seen"] = "within month"
        elif "Long" in status_type:
            status_info["is_online"] = False
            status_info["last_seen"] = "long time ago"
        else:
            status_info["is_online"] = False

    return json.dumps(status_info, indent=2)


async def search_public_chats(client: TelegramClient, query: str) -> str:
    """Search for public chats/channels.

    Args:
        client: The user's Telegram client
        query: Search query

    Returns:
        JSON string with matching public chats
    """
    from telethon.tl.functions.contacts import SearchRequest

    result = await client(SearchRequest(
        q=query,
        limit=50,
    ))

    chats = []
    for chat in result.chats:
        chat_info = {
            "id": chat.id,
            "title": getattr(chat, "title", None),
            "username": getattr(chat, "username", None),
            "participants_count": getattr(chat, "participants_count", None),
        }

        if hasattr(chat, "broadcast"):
            chat_info["type"] = "channel" if chat.broadcast else "supergroup"
        else:
            chat_info["type"] = "group"

        chats.append(chat_info)

    users = []
    for user in result.users:
        if isinstance(user, User):
            users.append({
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "type": "user",
            })

    return json.dumps({
        "chats": chats,
        "users": users,
        "query": query,
        "chat_count": len(chats),
        "user_count": len(users),
    }, indent=2)


async def resolve_username(client: TelegramClient, username: str) -> str:
    """Resolve a username to get user/channel ID.

    Args:
        client: The user's Telegram client
        username: Username to resolve (with or without @)

    Returns:
        JSON string with resolved entity info
    """
    from telethon.tl.functions.contacts import ResolveUsernameRequest
    from telethon.tl.types import Channel

    username = username.lstrip("@")

    result = await client(ResolveUsernameRequest(username=username))

    if result.users:
        user = result.users[0]
        return json.dumps({
            "type": "user",
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "is_bot": user.bot,
        }, indent=2)

    if result.chats:
        chat = result.chats[0]
        chat_type = "channel"
        if isinstance(chat, Channel):
            chat_type = "channel" if chat.broadcast else "supergroup"

        return json.dumps({
            "type": chat_type,
            "id": chat.id,
            "title": getattr(chat, "title", None),
            "username": getattr(chat, "username", None),
        }, indent=2)

    return json.dumps({
        "error": "Username not found",
        "username": username,
    }, indent=2)


async def get_sticker_sets(client: TelegramClient) -> str:
    """Get user's saved sticker sets.

    Args:
        client: The user's Telegram client

    Returns:
        JSON string with sticker sets
    """
    from telethon.tl.functions.messages import GetAllStickersRequest

    result = await client(GetAllStickersRequest(hash=0))

    sticker_sets = []
    for s in result.sets:
        sticker_sets.append({
            "id": s.id,
            "title": s.title,
            "short_name": s.short_name,
            "count": s.count,
            "is_animated": s.animated,
            "is_video": getattr(s, "videos", False),
        })

    return json.dumps({
        "sticker_sets": sticker_sets,
        "count": len(sticker_sets),
    }, indent=2)


async def get_bot_info(client: TelegramClient, bot_username: str) -> str:
    """Get information about a bot.

    Args:
        client: The user's Telegram client
        bot_username: Bot username

    Returns:
        JSON string with bot info
    """
    entity = await client.get_entity(bot_username)

    if not isinstance(entity, User) or not entity.bot:
        return json.dumps({"error": "Not a bot"}, indent=2)

    # Get full user info
    full = await client(GetFullUserRequest(id=entity))

    bot_info: dict[str, Any] = {
        "id": entity.id,
        "first_name": entity.first_name,
        "username": entity.username,
        "is_verified": entity.verified,
        "is_premium": getattr(entity, "premium", False),
    }

    if full.full_user.bot_info:
        bi = full.full_user.bot_info
        bot_info["description"] = bi.description
        bot_info["commands"] = [
            {"command": cmd.command, "description": cmd.description}
            for cmd in (bi.commands or [])
        ]

    return json.dumps(bot_info, indent=2)
