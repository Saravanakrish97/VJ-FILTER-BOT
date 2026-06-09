import asyncio
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from pyrogram.errors import (
    FloodWait,
    UserIsBlocked
)

from pyrogram.raw.functions.messages import SetTyping
from pyrogram.raw.types import SendMessageTypingAction

from database.anondb import anondb

from plugins.Extra.anonutils import (
    send_new_user_log,
    send_profile_complete_log,
    send_pair_log,
    send_next_log,
    send_end_log,
    send_anon_message_log,
    relay_to_partner
)

SEARCH_TIMEOUT = 120
IDLE_CHAT_LIMIT = 1800

waiting_users = set()
sessions = {}
chat_timers = {}
search_tasks = {}

profile_states = {}
profile_data = {}

waiting_lock = asyncio.Lock()

logged_users = set()


async def send_typing(client, user_id):

    try:

        await client.invoke(
            SetTyping(
                peer=await client.resolve_peer(user_id),
                action=SendMessageTypingAction()
            )
        )

    except:
        pass


# AUTO IDLE CLOSE

async def idle_chat_checker(client):

    while True:

        await asyncio.sleep(60)

        now = datetime.utcnow()

        checked = set()

        for user_id, last_time in list(chat_timers.items()):

            if user_id in checked:
                continue

            partner = sessions.get(user_id)

            if not partner:
                continue

            checked.add(user_id)
            checked.add(partner)

            diff = (now - last_time).total_seconds()

            if diff >= IDLE_CHAT_LIMIT:

                sessions.pop(user_id, None)
                sessions.pop(partner, None)

                chat_timers.pop(user_id, None)
                chat_timers.pop(partner, None)

                await anondb.remove_partner(user_id)
                await anondb.remove_partner(partner)

                user1 = await client.get_users(user_id)
                user2 = await client.get_users(partner)

                await send_end_log(
                    client,
                    user1,
                    user2
                )

                try:

                    await client.send_message(
                        user_id,
                        """
⌛ நீண்ட நேரமாக எந்த message-மும் அனுப்பப்படவில்லை

❌ உரையாடல் தானாக முடிக்கப்பட்டது

Chat closed automatically due to inactivity.
"""
                    )

                except Exception as e:

                    print(f"IDLE ERROR USER {user_id}: {e}")

                try:

                    await client.send_message(
                        partner,
                        """
⌛ நீண்ட நேரமாக எந்த message-மும் அனுப்பப்படவில்லை

❌ உரையாடல் தானாக முடிக்கப்பட்டது

Chat closed automatically due to inactivity.
"""
                    )

                except Exception as e:

                    print(f"IDLE ERROR PARTNER {partner}: {e}")


@Client.on_message(filters.command("start") & filters.private, group=-1)
async def start_idle_checker(client, message):

    if not hasattr(client, "idle_checker_started"):

        client.idle_checker_started = True

        asyncio.create_task(
            idle_chat_checker(client)
        )


# PROFILE

@Client.on_message(filters.private & filters.command("profile"))
async def profile_cmd(client, message):

    user_id = message.from_user.id

    await anondb.create_user(user_id)

    if user_id not in logged_users:

        await send_new_user_log(
            client,
            message.from_user
        )

        logged_users.add(user_id)

    user = await anondb.get_user(user_id)

    if user.get("profile", {}).get("name"):

        return await message.reply_text(
            """
⚠️ உங்கள் profile ஏற்கனவே உருவாக்கப்பட்டுள்ளது

Your profile is already completed.
"""
        )

    profile_states[user_id] = "name"
    profile_data[user_id] = {}

    await message.reply_text(
        """
👤 உங்கள் பெயரை அனுப்புங்கள்

Send your name:
"""
    )


@Client.on_message(filters.private, group=1)
async def profile_handler(client, message):

    user_id = message.from_user.id

    if user_id not in profile_states:
        return

    if message.text and message.text.startswith("/"):
        return

    if not message.text:

        return await message.reply_text(
            """
⚠️ எழுத்து மட்டும் அனுப்பவும்

Please send text only.
"""
        )

    text = message.text.strip()

    step = profile_states[user_id]

    if step == "name":

        profile_data[user_id]["name"] = text

        profile_states[user_id] = "age"

        return await message.reply_text(
            """
🎂 உங்கள் வயதை அனுப்புங்கள்

Send your age:
"""
        )

    elif step == "age":

        if not text.isdigit():

            return await message.reply_text(
                """
⚠️ சரியான வயதை அனுப்புங்கள்

Send valid age.
"""
            )

        age = int(text)

        if age < 10 or age > 99:

            return await message.reply_text(
                """
⚠️ வயது 10 முதல் 99 வரை இருக்க வேண்டும்

Age must be between 10 - 99.
"""
            )

        profile_data[user_id]["age"] = age

        profile_states[user_id] = "gender"

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "Male",
                    callback_data="gender_male"
                ),
                InlineKeyboardButton(
                    "Female",
                    callback_data="gender_female"
                )
            ],
            [
                InlineKeyboardButton(
                    "Other",
                    callback_data="gender_other"
                )
            ]
        ])

        return await message.reply_text(
            """
🚻 உங்கள் பாலினத்தை தேர்வு செய்யுங்கள்

Select your gender:
""",
            reply_markup=buttons
        )

    elif step == "location":

        profile_data[user_id]["location"] = text

        await anondb.set_profile(
            user_id,
            {
                "name": profile_data[user_id]["name"],
                "age": profile_data[user_id]["age"],
                "gender": profile_data[user_id]["gender"],
                "location": profile_data[user_id]["location"]
            }
        )

        profile_states.pop(user_id, None)
        profile_data.pop(user_id, None)

        await send_profile_complete_log(
            client,
            message.from_user
        )

        return await message.reply_text(
            """
✅ உங்கள் profile வெற்றிகரமாக சேமிக்கப்பட்டது

🔍 புதிய partner ஐ தேட /chat பயன்படுத்தவும்

Your profile has been completed.

Use /chat to find partner.
"""
        )
