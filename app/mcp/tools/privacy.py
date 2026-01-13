"""Privacy and settings MCP tools."""

import json
from typing import Any

from telethon import TelegramClient
from telethon.tl.types import (
    InputPrivacyKeyStatusTimestamp,
    InputPrivacyKeyChatInvite,
    InputPrivacyKeyPhoneCall,
    InputPrivacyKeyPhoneNumber,
    InputPrivacyKeyProfilePhoto,
    InputPrivacyKeyForwards,
    InputPrivacyKeyBirthday,
    InputPrivacyValueAllowAll,
    InputPrivacyValueAllowContacts,
    InputPrivacyValueDisallowAll,
    InputPrivacyValueAllowUsers,
    InputPrivacyValueDisallowUsers,
    User,
)
from telethon.tl.functions.account import (
    GetPrivacyRequest,
    SetPrivacyRequest,
)
from telethon.tl.functions.messages import (
    GetDialogsRequest,
)


PRIVACY_KEY_MAP = {
    "status": InputPrivacyKeyStatusTimestamp,
    "chat_invite": InputPrivacyKeyChatInvite,
    "phone_call": InputPrivacyKeyPhoneCall,
    "phone_number": InputPrivacyKeyPhoneNumber,
    "profile_photo": InputPrivacyKeyProfilePhoto,
    "forwards": InputPrivacyKeyForwards,
    "birthday": InputPrivacyKeyBirthday,
}


async def get_privacy_settings(client: TelegramClient) -> str:
    """Get current privacy settings.

    Args:
        client: The user's Telegram client

    Returns:
        JSON string with privacy settings
    """
    settings = {}

    for key_name, key_class in PRIVACY_KEY_MAP.items():
        try:
            result = await client(GetPrivacyRequest(key=key_class()))

            # Parse the rules
            rule_types = []
            for rule in result.rules:
                rule_types.append(type(rule).__name__)

            settings[key_name] = {
                "rules": rule_types,
            }
        except Exception as e:
            settings[key_name] = {"error": str(e)}

    return json.dumps({
        "privacy_settings": settings,
    }, indent=2)


async def set_privacy_settings(
    client: TelegramClient,
    key: str,
    allow_users: list[int | str] | None = None,
    disallow_users: list[int | str] | None = None,
) -> str:
    """Set privacy settings for a specific key.

    Args:
        client: The user's Telegram client
        key: Privacy key (status, chat_invite, phone_call, phone_number, profile_photo, forwards, birthday)
        allow_users: List of user IDs/usernames to allow
        disallow_users: List of user IDs/usernames to disallow

    Returns:
        JSON string with result
    """
    if key not in PRIVACY_KEY_MAP:
        return json.dumps({
            "error": f"Invalid key. Valid keys: {', '.join(PRIVACY_KEY_MAP.keys())}",
        }, indent=2)

    key_class = PRIVACY_KEY_MAP[key]

    # Build rules
    rules = []

    if allow_users:
        users = []
        for user_id in allow_users:
            try:
                entity = await client.get_entity(user_id)
                if isinstance(entity, User):
                    users.append(entity)
            except Exception:
                pass
        if users:
            rules.append(InputPrivacyValueAllowUsers(users=users))

    if disallow_users:
        users = []
        for user_id in disallow_users:
            try:
                entity = await client.get_entity(user_id)
                if isinstance(entity, User):
                    users.append(entity)
            except Exception:
                pass
        if users:
            rules.append(InputPrivacyValueDisallowUsers(users=users))

    # If no specific users, default to contacts only
    if not rules:
        rules.append(InputPrivacyValueAllowContacts())

    await client(SetPrivacyRequest(
        key=key_class(),
        rules=rules,
    ))

    return json.dumps({
        "success": True,
        "key": key,
        "rules_applied": len(rules),
    }, indent=2)


async def mute_chat(client: TelegramClient, chat_id: int | str) -> str:
    """Mute notifications for a chat.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username

    Returns:
        JSON string with result
    """
    from telethon.tl.functions.account import UpdateNotifySettingsRequest
    from telethon.tl.types import InputNotifyPeer, InputPeerNotifySettings

    entity = await client.get_entity(chat_id)

    # Mute for a very long time (essentially forever)
    mute_until = 2147483647  # Max int32, far future

    await client(UpdateNotifySettingsRequest(
        peer=InputNotifyPeer(peer=entity),
        settings=InputPeerNotifySettings(
            mute_until=mute_until,
            silent=True,
        ),
    ))

    return json.dumps({
        "success": True,
        "chat_id": entity.id,
        "muted": True,
    }, indent=2)


async def unmute_chat(client: TelegramClient, chat_id: int | str) -> str:
    """Unmute notifications for a chat.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username

    Returns:
        JSON string with result
    """
    from telethon.tl.functions.account import UpdateNotifySettingsRequest
    from telethon.tl.types import InputNotifyPeer, InputPeerNotifySettings

    entity = await client.get_entity(chat_id)

    await client(UpdateNotifySettingsRequest(
        peer=InputNotifyPeer(peer=entity),
        settings=InputPeerNotifySettings(
            mute_until=0,
            silent=False,
        ),
    ))

    return json.dumps({
        "success": True,
        "chat_id": entity.id,
        "muted": False,
    }, indent=2)


async def archive_chat(client: TelegramClient, chat_id: int | str) -> str:
    """Archive a chat.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username

    Returns:
        JSON string with result
    """
    from telethon.tl.functions.folders import EditPeerFoldersRequest
    from telethon.tl.types import InputFolderPeer

    entity = await client.get_entity(chat_id)

    await client(EditPeerFoldersRequest(
        folder_peers=[InputFolderPeer(
            peer=entity,
            folder_id=1,  # 1 = Archive folder
        )],
    ))

    return json.dumps({
        "success": True,
        "chat_id": entity.id,
        "archived": True,
    }, indent=2)


async def unarchive_chat(client: TelegramClient, chat_id: int | str) -> str:
    """Unarchive a chat.

    Args:
        client: The user's Telegram client
        chat_id: Chat ID or username

    Returns:
        JSON string with result
    """
    from telethon.tl.functions.folders import EditPeerFoldersRequest
    from telethon.tl.types import InputFolderPeer

    entity = await client.get_entity(chat_id)

    await client(EditPeerFoldersRequest(
        folder_peers=[InputFolderPeer(
            peer=entity,
            folder_id=0,  # 0 = Main folder (unarchive)
        )],
    ))

    return json.dumps({
        "success": True,
        "chat_id": entity.id,
        "archived": False,
    }, indent=2)
