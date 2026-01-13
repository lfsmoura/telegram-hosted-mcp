"""Chat and group management MCP tools."""

import json
from typing import Any

from telethon import TelegramClient
from telethon.tl.types import (
    Channel,
    Chat,
    User,
)
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    EditAdminRequest,
    EditBannedRequest,
    GetAdminLogRequest,
    GetParticipantsRequest,
    InviteToChannelRequest,
    JoinChannelRequest,
    LeaveChannelRequest,
    EditTitleRequest as ChannelEditTitleRequest,
    DeleteHistoryRequest,
)
from telethon.tl.functions.messages import (
    CreateChatRequest,
    AddChatUserRequest,
    DeleteChatUserRequest,
    EditChatTitleRequest,
    ExportChatInviteRequest,
    ImportChatInviteRequest,
    CheckChatInviteRequest,
)
from telethon.tl.types import (
    ChatAdminRights,
    ChatBannedRights,
    ChannelParticipantsAdmins,
    ChannelParticipantsBanned,
    ChannelParticipantsSearch,
)


async def get_chats(
    client: TelegramClient,
    page: int = 1,
    page_size: int = 20,
) -> str:
    """Get paginated list of chats.

    Args:
        client: The user's Telegram client
        page: Page number (1-indexed)
        page_size: Number of chats per page

    Returns:
        JSON string with paginated list of chats
    """
    offset = (page - 1) * page_size
    dialogs = await client.get_dialogs(limit=offset + page_size)

    # Get the page slice
    page_dialogs = dialogs[offset:offset + page_size]

    chats = []
    for dialog in page_dialogs:
        entity = dialog.entity
        chat_info = {
            "id": dialog.id,
            "name": dialog.name,
            "unread_count": dialog.unread_count,
        }

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

        chats.append(chat_info)

    return json.dumps({
        "chats": chats,
        "page": page,
        "page_size": page_size,
        "count": len(chats),
    }, indent=2)


async def list_chats(
    client: TelegramClient,
    chat_type: str | None = None,
    limit: int = 20,
) -> str:
    """List all Telegram chats (dialogs) for the user with optional filtering.

    Args:
        client: The user's Telegram client
        chat_type: Filter by type: "private", "group", "supergroup", "channel"
        limit: Maximum number of chats to return

    Returns:
        JSON string with list of chats
    """
    dialogs = await client.get_dialogs(limit=limit * 3 if chat_type else limit)

    chats = []
    for dialog in dialogs:
        if len(chats) >= limit:
            break

        entity = dialog.entity
        chat_info = {
            "id": dialog.id,
            "name": dialog.name,
            "unread_count": dialog.unread_count,
        }

        # Determine type
        if isinstance(entity, User):
            entity_type = "private"
            chat_info["username"] = entity.username
            chat_info["is_bot"] = entity.bot
        elif isinstance(entity, Chat):
            entity_type = "group"
            chat_info["participants_count"] = getattr(entity, "participants_count", None)
        elif isinstance(entity, Channel):
            entity_type = "channel" if entity.broadcast else "supergroup"
            chat_info["username"] = entity.username
            chat_info["participants_count"] = getattr(entity, "participants_count", None)
        else:
            continue

        chat_info["type"] = entity_type

        # Filter by type if specified
        if chat_type and entity_type != chat_type:
            continue

        # Last message preview
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
            "phone": "***" if entity.phone else None,
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

        try:
            full = await client.get_entity(entity)
            if hasattr(full, "about"):
                chat_info["about"] = full.about
        except Exception:
            pass

    return json.dumps(chat_info, indent=2)


async def create_group(
    client: TelegramClient,
    title: str,
    user_ids: list[int | str],
) -> str:
    """Create a new group chat.

    Args:
        client: The user's Telegram client
        title: Group title
        user_ids: List of user IDs or usernames to add

    Returns:
        JSON string with created group info
    """
    users = []
    for user_id in user_ids:
        try:
            user = await client.get_entity(user_id)
            users.append(user)
        except Exception as e:
            return json.dumps({"error": f"Could not find user {user_id}: {e}"}, indent=2)

    result = await client(CreateChatRequest(
        users=users,
        title=title,
    ))

    chat = result.chats[0]
    return json.dumps({
        "success": True,
        "chat_id": chat.id,
        "title": chat.title,
        "type": "group",
    }, indent=2)


async def invite_to_group(
    client: TelegramClient,
    group_id: int | str,
    user_ids: list[int | str],
) -> str:
    """Invite users to a group or channel.

    Args:
        client: The user's Telegram client
        group_id: Group/channel ID or username
        user_ids: List of user IDs or usernames to invite

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(group_id)

    users = []
    for user_id in user_ids:
        try:
            user = await client.get_entity(user_id)
            users.append(user)
        except Exception as e:
            return json.dumps({"error": f"Could not find user {user_id}: {e}"}, indent=2)

    if isinstance(entity, Channel):
        await client(InviteToChannelRequest(
            channel=entity,
            users=users,
        ))
    elif isinstance(entity, Chat):
        for user in users:
            await client(AddChatUserRequest(
                chat_id=entity.id,
                user_id=user,
                fwd_limit=100,
            ))

    return json.dumps({
        "success": True,
        "group_id": entity.id,
        "users_invited": len(users),
    }, indent=2)


async def create_channel(
    client: TelegramClient,
    title: str,
    about: str = "",
    megagroup: bool = False,
) -> str:
    """Create a new channel or supergroup.

    Args:
        client: The user's Telegram client
        title: Channel title
        about: Channel description
        megagroup: If True, create a supergroup instead of channel

    Returns:
        JSON string with created channel info
    """
    result = await client(CreateChannelRequest(
        title=title,
        about=about,
        megagroup=megagroup,
        broadcast=not megagroup,
    ))

    channel = result.chats[0]
    return json.dumps({
        "success": True,
        "channel_id": channel.id,
        "title": channel.title,
        "type": "supergroup" if megagroup else "channel",
    }, indent=2)


async def edit_chat_title(
    client: TelegramClient,
    chat_id: int | str,
    title: str,
) -> str:
    """Edit chat/channel title.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        title: New title

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)

    if isinstance(entity, Channel):
        await client(ChannelEditTitleRequest(
            channel=entity,
            title=title,
        ))
    elif isinstance(entity, Chat):
        await client(EditChatTitleRequest(
            chat_id=entity.id,
            title=title,
        ))
    else:
        return json.dumps({"error": "Cannot edit title of private chat"}, indent=2)

    return json.dumps({
        "success": True,
        "chat_id": entity.id,
        "new_title": title,
    }, indent=2)


async def leave_chat(client: TelegramClient, chat_id: int | str) -> str:
    """Leave a group or channel.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)

    if isinstance(entity, Channel):
        await client(LeaveChannelRequest(channel=entity))
    elif isinstance(entity, Chat):
        me = await client.get_me()
        await client(DeleteChatUserRequest(
            chat_id=entity.id,
            user_id=me,
        ))
    else:
        return json.dumps({"error": "Cannot leave a private chat"}, indent=2)

    return json.dumps({
        "success": True,
        "left_chat_id": entity.id,
    }, indent=2)


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


async def get_admins(client: TelegramClient, chat_id: int | str) -> str:
    """Get administrators of a group or channel.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username

    Returns:
        JSON string with list of admins
    """
    entity = await client.get_entity(chat_id)

    admins = []
    async for user in client.iter_participants(entity, filter=ChannelParticipantsAdmins):
        admins.append({
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
        })

    return json.dumps({
        "admins": admins,
        "count": len(admins),
        "chat_id": entity.id,
    }, indent=2)


async def get_banned_users(client: TelegramClient, chat_id: int | str) -> str:
    """Get banned users of a group or channel.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username

    Returns:
        JSON string with list of banned users
    """
    entity = await client.get_entity(chat_id)

    banned = []
    async for user in client.iter_participants(entity, filter=ChannelParticipantsBanned):
        banned.append({
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
        })

    return json.dumps({
        "banned_users": banned,
        "count": len(banned),
        "chat_id": entity.id,
    }, indent=2)


async def promote_admin(
    client: TelegramClient,
    chat_id: int | str,
    user_id: int | str,
) -> str:
    """Promote a user to admin in a group or channel.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        user_id: User ID or username to promote

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)
    user = await client.get_entity(user_id)

    admin_rights = ChatAdminRights(
        change_info=True,
        delete_messages=True,
        ban_users=True,
        invite_users=True,
        pin_messages=True,
        manage_call=True,
    )

    await client(EditAdminRequest(
        channel=entity,
        user_id=user,
        admin_rights=admin_rights,
        rank="Admin",
    ))

    return json.dumps({
        "success": True,
        "chat_id": entity.id,
        "user_id": user.id,
        "promoted": True,
    }, indent=2)


async def demote_admin(
    client: TelegramClient,
    chat_id: int | str,
    user_id: int | str,
) -> str:
    """Demote an admin in a group or channel.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        user_id: User ID or username to demote

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)
    user = await client.get_entity(user_id)

    # Remove all admin rights
    admin_rights = ChatAdminRights()

    await client(EditAdminRequest(
        channel=entity,
        user_id=user,
        admin_rights=admin_rights,
        rank="",
    ))

    return json.dumps({
        "success": True,
        "chat_id": entity.id,
        "user_id": user.id,
        "demoted": True,
    }, indent=2)


async def ban_user(
    client: TelegramClient,
    chat_id: int | str,
    user_id: int | str,
) -> str:
    """Ban a user from a group or channel.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        user_id: User ID or username to ban

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)
    user = await client.get_entity(user_id)

    banned_rights = ChatBannedRights(
        until_date=None,
        view_messages=True,
        send_messages=True,
        send_media=True,
        send_stickers=True,
        send_gifs=True,
        send_games=True,
        send_inline=True,
        embed_links=True,
    )

    await client(EditBannedRequest(
        channel=entity,
        participant=user,
        banned_rights=banned_rights,
    ))

    return json.dumps({
        "success": True,
        "chat_id": entity.id,
        "user_id": user.id,
        "banned": True,
    }, indent=2)


async def unban_user(
    client: TelegramClient,
    chat_id: int | str,
    user_id: int | str,
) -> str:
    """Unban a user from a group or channel.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        user_id: User ID or username to unban

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(chat_id)
    user = await client.get_entity(user_id)

    # Remove all restrictions
    banned_rights = ChatBannedRights()

    await client(EditBannedRequest(
        channel=entity,
        participant=user,
        banned_rights=banned_rights,
    ))

    return json.dumps({
        "success": True,
        "chat_id": entity.id,
        "user_id": user.id,
        "unbanned": True,
    }, indent=2)


async def get_invite_link(client: TelegramClient, chat_id: int | str) -> str:
    """Get the invite link for a group or channel.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username

    Returns:
        JSON string with invite link
    """
    entity = await client.get_entity(chat_id)

    result = await client(ExportChatInviteRequest(
        peer=entity,
        legacy_revoke_permanent=True,
    ))

    return json.dumps({
        "success": True,
        "chat_id": entity.id,
        "invite_link": result.link,
    }, indent=2)


async def export_chat_invite(client: TelegramClient, chat_id: int | str) -> str:
    """Export a new invite link for a group or channel.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username

    Returns:
        JSON string with new invite link
    """
    entity = await client.get_entity(chat_id)

    result = await client(ExportChatInviteRequest(
        peer=entity,
    ))

    return json.dumps({
        "success": True,
        "chat_id": entity.id,
        "invite_link": result.link,
    }, indent=2)


async def import_chat_invite(client: TelegramClient, hash: str) -> str:
    """Join a chat using an invite hash.

    Args:
        client: The user's Telegram client
        hash: Invite link hash (the part after t.me/+)

    Returns:
        JSON string with joined chat info
    """
    result = await client(ImportChatInviteRequest(hash=hash))

    chat = result.chats[0]
    return json.dumps({
        "success": True,
        "chat_id": chat.id,
        "title": getattr(chat, "title", None),
    }, indent=2)


async def join_chat_by_link(client: TelegramClient, link: str) -> str:
    """Join a chat using a full invite link.

    Args:
        client: The user's Telegram client
        link: Full invite link (e.g., https://t.me/+abc123 or https://t.me/channelname)

    Returns:
        JSON string with joined chat info
    """
    # Extract hash from link
    if "/+" in link:
        hash = link.split("/+")[-1]
        return await import_chat_invite(client, hash)
    else:
        # Public channel/group username
        username = link.split("/")[-1].lstrip("@")
        entity = await client.get_entity(username)

        if isinstance(entity, Channel):
            await client(JoinChannelRequest(channel=entity))

        return json.dumps({
            "success": True,
            "chat_id": entity.id,
            "title": getattr(entity, "title", None),
        }, indent=2)


async def subscribe_public_channel(client: TelegramClient, channel: str) -> str:
    """Subscribe to a public channel.

    Args:
        client: The user's Telegram client
        channel: Channel username

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(channel)

    if not isinstance(entity, Channel):
        return json.dumps({"error": "Not a channel"}, indent=2)

    await client(JoinChannelRequest(channel=entity))

    return json.dumps({
        "success": True,
        "channel_id": entity.id,
        "title": entity.title,
        "subscribed": True,
    }, indent=2)


async def get_recent_actions(
    client: TelegramClient,
    chat_id: int | str,
    limit: int = 50,
) -> str:
    """Get recent admin actions in a group or channel.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username
        limit: Maximum number of actions to return

    Returns:
        JSON string with recent admin actions
    """
    entity = await client.get_entity(chat_id)

    if not isinstance(entity, Channel):
        return json.dumps({"error": "Admin log only available for channels/supergroups"}, indent=2)

    result = await client(GetAdminLogRequest(
        channel=entity,
        q="",
        max_id=0,
        min_id=0,
        limit=limit,
    ))

    actions = []
    for event in result.events:
        action_info = {
            "id": event.id,
            "date": event.date.isoformat() if event.date else None,
            "user_id": event.user_id,
            "action_type": type(event.action).__name__,
        }
        actions.append(action_info)

    return json.dumps({
        "actions": actions,
        "count": len(actions),
        "chat_id": entity.id,
    }, indent=2)


# Contact-related tools (kept here for backwards compatibility)

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
