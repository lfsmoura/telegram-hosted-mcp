"""Contact management MCP tools."""

import json
from typing import Any

from telethon import TelegramClient
from telethon.tl.types import User, InputPhoneContact
from telethon.tl.functions.contacts import (
    GetContactsRequest,
    ImportContactsRequest,
    DeleteContactsRequest,
    BlockRequest,
    UnblockRequest,
    GetBlockedRequest,
    SearchRequest,
    ResolveUsernameRequest,
)


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
            "phone": "***" if user.phone else None,  # Never expose actual phone
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


async def add_contact(
    client: TelegramClient,
    phone: str,
    first_name: str,
    last_name: str = "",
) -> str:
    """Add a new contact.

    Args:
        client: The user's Telegram client
        phone: Phone number (international format)
        first_name: Contact's first name
        last_name: Contact's last name (optional)

    Returns:
        JSON string with result
    """
    import random

    contact = InputPhoneContact(
        client_id=random.randint(0, 2**62),
        phone=phone,
        first_name=first_name,
        last_name=last_name,
    )

    result = await client(ImportContactsRequest([contact]))

    if result.users:
        user = result.users[0]
        return json.dumps({
            "success": True,
            "user_id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
        }, indent=2)
    else:
        return json.dumps({
            "success": False,
            "error": "User not found on Telegram",
            "imported_count": len(result.imported),
        }, indent=2)


async def delete_contact(client: TelegramClient, user_id: int | str) -> str:
    """Delete a contact.

    Args:
        client: The user's Telegram client
        user_id: User ID or username to delete

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(user_id)

    if not isinstance(entity, User):
        return json.dumps({"error": "Not a user"}, indent=2)

    await client(DeleteContactsRequest(id=[entity]))

    return json.dumps({
        "success": True,
        "deleted_user_id": entity.id,
    }, indent=2)


async def block_user(client: TelegramClient, user_id: int | str) -> str:
    """Block a user.

    Args:
        client: The user's Telegram client
        user_id: User ID or username to block

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(user_id)

    if not isinstance(entity, User):
        return json.dumps({"error": "Not a user"}, indent=2)

    await client(BlockRequest(id=entity))

    return json.dumps({
        "success": True,
        "blocked_user_id": entity.id,
    }, indent=2)


async def unblock_user(client: TelegramClient, user_id: int | str) -> str:
    """Unblock a user.

    Args:
        client: The user's Telegram client
        user_id: User ID or username to unblock

    Returns:
        JSON string with result
    """
    entity = await client.get_entity(user_id)

    if not isinstance(entity, User):
        return json.dumps({"error": "Not a user"}, indent=2)

    await client(UnblockRequest(id=entity))

    return json.dumps({
        "success": True,
        "unblocked_user_id": entity.id,
    }, indent=2)


async def import_contacts(
    client: TelegramClient,
    contacts: list[dict],
) -> str:
    """Import multiple contacts.

    Args:
        client: The user's Telegram client
        contacts: List of contacts with phone, first_name, last_name

    Returns:
        JSON string with result
    """
    import random

    input_contacts = []
    for c in contacts:
        input_contacts.append(InputPhoneContact(
            client_id=random.randint(0, 2**62),
            phone=c.get("phone", ""),
            first_name=c.get("first_name", ""),
            last_name=c.get("last_name", ""),
        ))

    result = await client(ImportContactsRequest(input_contacts))

    imported_users = []
    for user in result.users:
        imported_users.append({
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
        })

    return json.dumps({
        "success": True,
        "imported_count": len(result.imported),
        "retry_contacts": len(result.retry_contacts),
        "users": imported_users,
    }, indent=2)


async def export_contacts(client: TelegramClient) -> str:
    """Export all contacts.

    Args:
        client: The user's Telegram client

    Returns:
        JSON string with all contacts
    """
    result = await client.get_contacts()

    contacts = []
    for user in result:
        contacts.append({
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "phone": "***" if user.phone else None,  # Never expose actual phone
            "is_mutual_contact": user.mutual_contact,
            "is_bot": user.bot,
            "is_verified": user.verified,
        })

    return json.dumps({
        "contacts": contacts,
        "count": len(contacts),
        "export_format": "json",
    }, indent=2)


async def get_blocked_users(client: TelegramClient) -> str:
    """Get list of blocked users.

    Args:
        client: The user's Telegram client

    Returns:
        JSON string with blocked users
    """
    result = await client(GetBlockedRequest(
        offset=0,
        limit=100,
    ))

    blocked = []
    for blocked_user in result.blocked:
        # Find user in the users list
        user = next(
            (u for u in result.users if u.id == blocked_user.peer_id.user_id),
            None
        )
        if user and isinstance(user, User):
            blocked.append({
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "blocked_date": blocked_user.date.isoformat() if blocked_user.date else None,
            })

    return json.dumps({
        "blocked_users": blocked,
        "count": len(blocked),
    }, indent=2)


async def get_contact_ids(client: TelegramClient) -> str:
    """Get list of all contact IDs.

    Args:
        client: The user's Telegram client

    Returns:
        JSON string with contact IDs
    """
    result = await client.get_contacts()

    contact_ids = [user.id for user in result]

    return json.dumps({
        "contact_ids": contact_ids,
        "count": len(contact_ids),
    }, indent=2)


async def get_direct_chat_by_contact(
    client: TelegramClient,
    contact_query: str,
) -> str:
    """Find direct chat with a contact by name or username.

    Args:
        client: The user's Telegram client
        contact_query: Contact name or username to search for

    Returns:
        JSON string with chat info
    """
    # First search in contacts
    contacts = await client.get_contacts()

    query_lower = contact_query.lower().lstrip("@")
    matched_user = None

    for user in contacts:
        name = f"{user.first_name or ''} {user.last_name or ''}".lower()
        username = (user.username or "").lower()

        if query_lower in name or query_lower == username:
            matched_user = user
            break

    if not matched_user:
        # Try to resolve as username
        try:
            entity = await client.get_entity(contact_query)
            if isinstance(entity, User):
                matched_user = entity
        except Exception:
            pass

    if not matched_user:
        return json.dumps({
            "error": "Contact not found",
            "query": contact_query,
        }, indent=2)

    # Get the dialog with this user
    dialogs = await client.get_dialogs()
    dialog = next(
        (d for d in dialogs if d.entity and d.entity.id == matched_user.id),
        None
    )

    result = {
        "user_id": matched_user.id,
        "first_name": matched_user.first_name,
        "last_name": matched_user.last_name,
        "username": matched_user.username,
        "has_dialog": dialog is not None,
    }

    if dialog:
        result["unread_count"] = dialog.unread_count
        if dialog.message:
            result["last_message_date"] = (
                dialog.message.date.isoformat() if dialog.message.date else None
            )

    return json.dumps(result, indent=2)


async def get_contact_chats(
    client: TelegramClient,
    contact_id: int | str,
) -> str:
    """Get all chats involving a specific contact.

    Args:
        client: The user's Telegram client
        contact_id: Contact user ID or username

    Returns:
        JSON string with chats involving this contact
    """
    entity = await client.get_entity(contact_id)

    if not isinstance(entity, User):
        return json.dumps({"error": "Not a user"}, indent=2)

    # Find direct chat
    dialogs = await client.get_dialogs()

    chats = []

    # Check for direct chat
    direct_dialog = next(
        (d for d in dialogs if d.entity and d.entity.id == entity.id),
        None
    )
    if direct_dialog:
        chats.append({
            "type": "direct",
            "chat_id": direct_dialog.id,
            "name": direct_dialog.name,
            "unread_count": direct_dialog.unread_count,
        })

    # Check for groups/channels where this user is a member
    # Note: This is limited as we can't efficiently check all groups
    for dialog in dialogs:
        if dialog.is_group or dialog.is_channel:
            try:
                # Check if user is in this group (limited check)
                participants = await client.get_participants(dialog.entity, limit=200)
                if any(p.id == entity.id for p in participants):
                    chats.append({
                        "type": "group" if dialog.is_group else "channel",
                        "chat_id": dialog.id,
                        "name": dialog.name,
                    })
            except Exception:
                # May not have permission to get participants
                continue

    return json.dumps({
        "contact_id": entity.id,
        "contact_name": f"{entity.first_name or ''} {entity.last_name or ''}".strip(),
        "chats": chats,
        "count": len(chats),
    }, indent=2)
