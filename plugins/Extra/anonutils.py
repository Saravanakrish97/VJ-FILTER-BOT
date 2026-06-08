from datetime import datetime
from pyrogram.errors import FloodWait, UserIsBlocked
from info import ANON_LOGS, LOG_CHANNEL


def clickable_mention(user):
    return f"[{user.first_name}](tg://user?id={user.id})"


async def send_new_user_log(client, user):

    text = f"""
🆕 **புதிய பயனர் இணைந்துள்ளார்**

👤 **User:** {clickable_mention(user)}
🆔 **User ID:** `{user.id}`
📝 **Username:** @{user.username if user.username else 'No Username'}
"""

    await client.send_message(
        LOG_CHANNEL,
        text,
        disable_web_page_preview=True
    )


async def send_profile_complete_log(client, user):

    text = f"""
✅ **Profile Completed**

👤 **User:** {clickable_mention(user)}
🆔 **User ID:** `{user.id}`
📝 **Username:** @{user.username if user.username else 'No Username'}
"""

    await client.send_message(
        LOG_CHANNEL,
        text,
        disable_web_page_preview=True
    )


async def send_pair_log(client, user1, user2):

    text = f"""
🤝 **புதிய இணைப்பு உருவாக்கப்பட்டது**

👤 **User 1:** {clickable_mention(user1)} `[ID: {user1.id}]`
👤 **User 2:** {clickable_mention(user2)} `[ID: {user2.id}]`
"""

    await client.send_message(
        LOG_CHANNEL,
        text,
        disable_web_page_preview=True
    )


async def send_next_log(client, user1, user2):

    text = f"""
⏭ **Partner மாற்றப்பட்டது**

👤 **User:** {clickable_mention(user1)} `[ID: {user1.id}]`
👤 **Previous Partner:** {clickable_mention(user2)} `[ID: {user2.id}]`
"""

    await client.send_message(
        LOG_CHANNEL,
        text,
        disable_web_page_preview=True
    )


async def send_end_log(client, user1, user2):

    text = f"""
🔌 **உரையாடல் முடிந்தது**

👤 **User:** {clickable_mention(user1)} `[ID: {user1.id}]`
👤 **Partner:** {clickable_mention(user2)} `[ID: {user2.id}]`
"""

    await client.send_message(
        LOG_CHANNEL,
        text,
        disable_web_page_preview=True
    )


async def send_anon_message_log(client, sender, message):

    try:

        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        if message.text:
            msg = message.text

        elif message.caption:
            msg = message.caption

        else:
            msg = "Media Message"

        log_text = f"""
Logs for chatbot:

[{current_time}]

From: {clickable_mention(sender)}

💬 Text: {msg}
"""

        await client.send_message(
            ANON_LOGS,
            log_text,
            disable_web_page_preview=True
        )

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
