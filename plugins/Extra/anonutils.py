from datetime import datetime

from pyrogram.errors import (
    FloodWait,
    UserIsBlocked
)

from info import ANON_LOGS, LOG_CHANNEL


def clickable_mention(user):

    return f"[{user.first_name}](tg://user?id={user.id})"


async def send_new_user_log(client, user):

    text = f"""
🆕 New User Joined

👤 User: {clickable_mention(user)}
🆔 User ID: `{user.id}`
📝 Username: @{user.username if user.username else 'No Username'}
"""

    await client.send_message(
        LOG_CHANNEL,
        text,
        disable_web_page_preview=True
    )


async def send_profile_complete_log(client, user):

    text = f"""
✅ Profile Completed

👤 User: {clickable_mention(user)}
🆔 User ID: `{user.id}`
📝 Username: @{user.username if user.username else 'No Username'}
"""

    await client.send_message(
        LOG_CHANNEL,
        text,
        disable_web_page_preview=True
    )


async def send_pair_log(client, user1, user2):

    text = f"""
🤝 New Chat Connection Created

👤 User 1: {clickable_mention(user1)} `[ID: {user1.id}]`
👤 User 2: {clickable_mention(user2)} `[ID: {user2.id}]`
"""

    await client.send_message(
        LOG_CHANNEL,
        text,
        disable_web_page_preview=True
    )


async def send_next_log(client, user1, user2):

    text = f"""
⏭ Partner Skipped

👤 User: {clickable_mention(user1)} `[ID: {user1.id}]`
👤 Previous Partner: {clickable_mention(user2)} `[ID: {user2.id}]`
"""

    await client.send_message(
        LOG_CHANNEL,
        text,
        disable_web_page_preview=True
    )


async def send_end_log(client, user1, user2):

    text = f"""
🔌 Chat Ended

👤 User: {clickable_mention(user1)} `[ID: {user1.id}]`
👤 Partner: {clickable_mention(user2)} `[ID: {user2.id}]`
"""

    await client.send_message(
        LOG_CHANNEL,
        text,
        disable_web_page_preview=True
    )


async def send_anon_message_log(client, sender, message):

    try:

        current_time = datetime.utcnow().strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

        msg_type = "Unknown"

        if message.text:
            msg_type = "Text"
            msg = message.text

        elif message.photo:
            msg_type = "Photo"
            msg = message.caption or "Photo"

        elif message.video:
            msg_type = "Video"
            msg = message.caption or "Video"

        elif message.animation:
            msg_type = "GIF"
            msg = message.caption or "GIF"

        elif message.voice:
            msg_type = "Voice"
            msg = "Voice Message"

        elif message.audio:
            msg_type = "Audio"
            msg = message.caption or "Audio"

        elif message.document:
            msg_type = "Document"
            msg = message.caption or "Document"

        elif message.sticker:
            msg_type = "Sticker"
            msg = "Sticker"

        else:
            msg = "Unsupported Media"

        log_text = f"""
Anonymous Chat Logs

[{current_time}]

👤 From: {clickable_mention(sender)}
🆔 User ID: `{sender.id}`

📦 Type: {msg_type}

💬 Content:
{msg}
"""

        await client.send_message(
            ANON_LOGS,
            log_text,
            disable_web_page_preview=True
        )

        await message.copy(ANON_LOGS)

    except Exception as e:

        print("ANON LOG ERROR:", e)


async def relay_to_partner(client, message, partner_id):

    try:

        await message.copy(partner_id)

    except FloodWait as e:

        import asyncio

        await asyncio.sleep(e.value)

    except UserIsBlocked:

        pass

    except Exception as e:

        print("RELAY ERROR:", e)
