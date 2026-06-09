import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, UserIsBlocked

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


@Client.on_callback_query(filters.regex("^gender_"))
async def gender_callback(client, query):

    user_id = query.from_user.id

    if user_id not in profile_data:
        return

    gender = query.data.split("_")[1]

    profile_data[user_id]["gender"] = gender.capitalize()

    profile_states[user_id] = "location"

    await query.answer(
        f"{gender.capitalize()} selected"
    )

    await query.message.reply_text(
        """
📍 உங்கள் இருப்பிடத்தை அனுப்புங்கள்

Send your location:
"""
    )


@Client.on_message(filters.private & filters.command("chat"))
async def search_partner(client, message):

    user_id = message.from_user.id

    user = await anondb.get_user(user_id)

    if not user.get("profile", {}).get("name"):

        return await message.reply_text(
            """
⚠️ முதலில் profile உருவாக்கவும்

Complete profile first using /profile
"""
        )

    async with waiting_lock:

        if user_id in sessions:

            return await message.reply_text(
                """
⚠️ நீங்கள் ஏற்கனவே ஒருவருடன் இணைக்கப்பட்டுள்ளீர்கள்

You are already connected.
"""
            )

        if user_id in waiting_users:

            return await message.reply_text(
                """
⚠️ Partner தேடல் நடைபெற்று வருகிறது

Already searching for partner...
"""
            )

        waiting_users.add(user_id)

        remaining = SEARCH_TIMEOUT

        search_msg = await message.reply_text(
            f"""
🔍 **புதிய partner தேடப்படுகிறது**

⏱️ **மீதமுள்ள நேரம்:** 02:00

⚠️ **தேடலை நிறுத்த /cancel பயன்படுத்தவும்**

Searching for partner...
"""
        )

        async def countdown():

            nonlocal remaining

            while remaining > 0:

                if user_id not in waiting_users:
                    return

                mins = remaining // 60
                secs = remaining % 60

                try:

                    dots = "." * ((remaining % 3) + 1)

                    await search_msg.edit_text(
                        f"""
🔍 **புதிய partner தேடப்படுகிறது{dots}**

⏱️ **மீதமுள்ள நேரம்:** {mins:02d}:{secs:02d}

⚠️ **தேடலை நிறுத்த /cancel பயன்படுத்தவும்**

Searching for partner...
"""
                    )

                except:
                    pass

                await asyncio.sleep(1)

                remaining -= 1

            if user_id in waiting_users:

                waiting_users.discard(user_id)

                try:

                    await search_msg.edit_text(
                        """
❌ **Partner கிடைக்கவில்லை**

🔁 **சிறிது நேரம் கழித்து மீண்டும் முயற்சிக்கவும்**

No partner found.
"""
                    )

                except:
                    pass

        search_tasks[user_id] = asyncio.create_task(
            countdown()
        )

        if len(waiting_users) >= 2:

            user1 = waiting_users.pop()
            user2 = waiting_users.pop()

            if user1 in search_tasks:
                search_tasks[user1].cancel()

            if user2 in search_tasks:
                search_tasks[user2].cancel()

            sessions[user1] = user2
            sessions[user2] = user1

            chat_timers[user1] = datetime.utcnow()
            chat_timers[user2] = datetime.utcnow()

            await anondb.set_partner(user1, user2)

            u1 = await anondb.get_user(user1)
            u2 = await anondb.get_user(user2)

            user1_obj = await client.get_users(user1)
            user2_obj = await client.get_users(user2)

            await send_pair_log(
                client,
                user1_obj,
                user2_obj
            )

            text1 = f"""
💘 **Partner கிடைத்துள்ளார்**

👤 பெயர் : {u2['profile']['name']}
🎂 வயது : {u2['profile']['age']}
🚻 பாலினம் : {u2['profile']['gender']}
📍 இடம் : {u2['profile']['location']}
"""

            text2 = f"""
💘 **Partner கிடைத்துள்ளார்**

👤 பெயர் : {u1['profile']['name']}
🎂 வயது : {u1['profile']['age']}
🚻 பாலினம் : {u1['profile']['gender']}
📍 இடம் : {u1['profile']['location']}
"""

            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⏭ Next",
                        callback_data="anon_next"
                    ),
                    InlineKeyboardButton(
                        "❌ End",
                        callback_data="anon_end"
                    )
                ]
            ])

            await client.send_message(
                user1,
                text1,
                reply_markup=buttons
            )

            await client.send_message(
                user2,
                text2,
                reply_markup=buttons
            )


@Client.on_message(filters.private & filters.command("cancel"))
async def cancel_search(client, message):

    user_id = message.from_user.id

    if user_id not in waiting_users:

        return await message.reply_text(
            """
⚠️ தற்போது எந்த தேடலும் நடைபெறவில்லை

You are not searching.
"""
        )

    waiting_users.discard(user_id)

    if user_id in search_tasks:
        search_tasks[user_id].cancel()

    await message.reply_text(
        """
❌ Partner தேடல் நிறுத்தப்பட்டது

🔍 மீண்டும் தேட /chat பயன்படுத்தவும்

Search cancelled.
"""
    )


@Client.on_message(filters.private & filters.command("next"))
async def next_command(client, message):

    user_id = message.from_user.id

    partner = sessions.get(user_id)

    if not partner:

        return await message.reply_text(
            """
⚠️ தற்போது எந்த partner உடனும் இணைக்கப்படவில்லை

You are not connected with any partner.

🔍 Use /chat to connect.
"""
        )

    sessions.pop(user_id, None)
    sessions.pop(partner, None)

    await anondb.remove_partner(user_id)
    await anondb.remove_partner(partner)

    user1 = await client.get_users(user_id)
    user2 = await client.get_users(partner)

    await send_next_log(
        client,
        user1,
        user2
    )

    await client.send_message(
        partner,
        """
❌ உங்கள் partner chat ஐ விட்டு வெளியேறிவிட்டார்

Partner left the chat.
"""
    )

    await message.reply_text(
        """
⏭ புதிய partner தேடப்படுகிறது

Searching for new partner...
"""
    )

    await search_partner(client, message)


@Client.on_message(filters.private & filters.command("end"))
async def end_command(client, message):

    user_id = message.from_user.id

    partner = sessions.get(user_id)

    if not partner:

        return await message.reply_text(
            """
⚠️ தற்போது எந்த partner உடனும் இணைக்கப்படவில்லை

You are not connected with any partner.

🔍 Use /chat to connect.
"""
        )

    sessions.pop(user_id, None)
    sessions.pop(partner, None)

    await anondb.remove_partner(user_id)
    await anondb.remove_partner(partner)

    user1 = await client.get_users(user_id)
    user2 = await client.get_users(partner)

    await send_end_log(
        client,
        user1,
        user2
    )

    await client.send_message(
        user_id,
        """
❌ உரையாடல் முடிந்தது

Chat ended.
"""
    )

    await client.send_message(
        partner,
        """
❌ உங்கள் partner உரையாடலை முடித்துவிட்டார்

Partner ended the chat.
"""
    )


@Client.on_callback_query(filters.regex("^anon_next$"))
async def anon_next_callback(client, query):

    user_id = query.from_user.id

    partner = sessions.get(user_id)

    if not partner:

        return await query.answer(
            "⚠️ தற்போது எந்த partner உடனும் இணைக்கப்படவில்லை",
            show_alert=True
        )

    sessions.pop(user_id, None)
    sessions.pop(partner, None)

    await anondb.remove_partner(user_id)
    await anondb.remove_partner(partner)

    user1 = await client.get_users(user_id)
    user2 = await client.get_users(partner)

    await send_next_log(
        client,
        user1,
        user2
    )

    await client.send_message(
        partner,
        "❌ Partner left the chat."
    )

    await client.send_message(
        user_id,
        "⏭ Searching for new partner..."
    )

    fake_message = query.message
    fake_message.from_user = query.from_user

    await search_partner(client, fake_message)

    await query.answer()


@Client.on_callback_query(filters.regex("^anon_end$"))
async def anon_end_callback(client, query):

    user_id = query.from_user.id

    partner = sessions.get(user_id)

    if not partner:

        return await query.answer(
            "⚠️ தற்போது எந்த partner உடனும் இணைக்கப்படவில்லை",
            show_alert=True
        )

    sessions.pop(user_id, None)
    sessions.pop(partner, None)

    await anondb.remove_partner(user_id)
    await anondb.remove_partner(partner)

    user1 = await client.get_users(user_id)
    user2 = await client.get_users(partner)

    await send_end_log(
        client,
        user1,
        user2
    )

    await client.send_message(
        user_id,
        "❌ Chat ended."
    )

    await client.send_message(
        partner,
        "❌ Partner ended the chat."
    )

    await query.answer("Chat ended")


@Client.on_message(filters.private, group=10)
async def relay_messages(client, message):

    user_id = message.from_user.id

    if message.text and message.text.startswith("/"):
        return

    if user_id in profile_states:
        return

    partner = sessions.get(user_id)

    if not partner:
        return

    chat_timers[user_id] = datetime.utcnow()
    chat_timers[partner] = datetime.utcnow()

    try:

        sender = await client.get_users(user_id)

        await send_anon_message_log(
            client,
            sender,
            message
        )

        await send_typing(client, partner)

        await asyncio.sleep(1)

        await relay_to_partner(
            client,
            message,
            partner
        )

    except FloodWait as e:

        await asyncio.sleep(e.value)

    except UserIsBlocked:

        sessions.pop(user_id, None)
        sessions.pop(partner, None)

    except Exception as e:

        print("[RELAY ERROR]", e)
