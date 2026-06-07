import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# CHANGE THIS ONLY
from database.anondb import anondb

waiting_users = []
profile_states = {}
profile_data = {}
sessions = {}

START_TEXT = """
✨ <b>Anonymous Chat Feature</b>

🔎 Random partner oda anonymous ah chat pannalam.

📌 Commands:

/search - Partner theda
/next - Next partner
/end - Chat end panna

🇮🇳 புதிய நண்பர்களை தேட
/search பயன்படுத்தவும்
"""

# ---------------- START ---------------- #

@Client.on_message(filters.private & filters.command("start"))
async def start(client, message):

    user_id = message.from_user.id

    await anondb.create_user(user_id)

    user = await anondb.get_user(user_id)

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔎 Start Anonymous Chat",
                callback_data="start_anon"
            )
        ]
    ])

    await message.reply_text(
        START_TEXT,
        reply_markup=buttons
    )

    if not user.get("name"):
        profile_states[user_id] = "name"

        await message.reply_text(
            "👤 Enter your name:"
        )

# ---------------- BUTTON ---------------- #

@Client.on_callback_query(filters.regex("start_anon"))
async def start_anon(client, query):

    user_id = query.from_user.id

    user = await anondb.get_user(user_id)

    if not user.get("name"):
        await query.message.reply_text(
            "⚠️ First complete profile setup."
        )
        return

    await query.message.reply_text(
        "🔎 Use /search to find partner"
    )

# ---------------- PROFILE ---------------- #

@Client.on_message(filters.private)
async def profile_handler(client, message):

    user_id = message.from_user.id

    if user_id not in profile_states:
        return

    text = message.text

    step = profile_states[user_id]

    if step == "name":

        profile_data[user_id] = {
            "name": text
        }

        profile_states[user_id] = "age"

        await message.reply_text(
            "🎂 Enter age:"
        )

    elif step == "age":

        if not text.isdigit():
            return await message.reply_text(
                "Send valid age"
            )

        profile_data[user_id]["age"] = text

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
            ]
        ])

        await message.reply_text(
            "🚻 Select gender",
            reply_markup=buttons
        )

    elif step == "location":

        profile_data[user_id]["location"] = text

        await anondb.set_profile(
            user_id,
            profile_data[user_id]
        )

        profile_states.pop(user_id)
        profile_data.pop(user_id)

        await message.reply_text(
            "✅ Profile completed.\n\nUse /search"
        )

# ---------------- GENDER ---------------- #

@Client.on_callback_query(filters.regex("gender_"))
async def gender_select(client, query):

    user_id = query.from_user.id

    gender = query.data.split("_")[1]

    profile_data[user_id]["gender"] = gender

    profile_states[user_id] = "location"

    await query.message.reply_text(
        "📍 Enter location:"
    )

# ---------------- SEARCH ---------------- #

@Client.on_message(filters.private & filters.command("search"))
async def search_partner(client, message):

    user_id = message.from_user.id

    user = await anondb.get_user(user_id)

    if not user.get("name"):
        return await message.reply_text(
            "⚠️ Complete profile first"
        )

    if user_id in sessions:
        return await message.reply_text(
            "⚠️ Already connected"
        )

    if user_id in waiting_users:
        return await message.reply_text(
            "🔎 Already searching..."
        )

    waiting_users.append(user_id)

    await message.reply_text(
        "🔎 Searching for partner..."
    )

    if len(waiting_users) >= 2:

        user1 = waiting_users.pop(0)
        user2 = waiting_users.pop(0)

        sessions[user1] = user2
        sessions[user2] = user1

        await anondb.set_partner(user1, user2)

        u1 = await anondb.get_user(user1)
        u2 = await anondb.get_user(user2)

        txt1 = f"""
🎉 Partner Connected

👤 Name: {u2['name']}
🎂 Age: {u2['age']}
🚻 Gender: {u2['gender']}
📍 Location: {u2['location']}
"""

        txt2 = f"""
🎉 Partner Connected

👤 Name: {u1['name']}
🎂 Age: {u1['age']}
🚻 Gender: {u1['gender']}
📍 Location: {u1['location']}
"""

        await client.send_message(user1, txt1)
        await client.send_message(user2, txt2)

# ---------------- NEXT ---------------- #

@Client.on_message(filters.private & filters.command("next"))
async def next_chat(client, message):

    user_id = message.from_user.id

    partner = sessions.get(user_id)

    if not partner:
        return await message.reply_text(
            "⚠️ You are not connected.\nUse /search"
        )

    sessions.pop(user_id, None)
    sessions.pop(partner, None)

    await anondb.clear_partner(user_id)
    await anondb.clear_partner(partner)

    await client.send_message(
        partner,
        "❌ Partner disconnected"
    )

    await message.reply_text(
        "🔎 Searching next partner..."
    )

    await search_partner(client, message)

# ---------------- END ---------------- #

@Client.on_message(filters.private & filters.command("end"))
async def end_chat(client, message):

    user_id = message.from_user.id

    partner = sessions.get(user_id)

    if not partner:
        return await message.reply_text(
            "⚠️ You are not connected.\nUse /search"
        )

    sessions.pop(user_id, None)
    sessions.pop(partner, None)

    await anondb.clear_partner(user_id)
    await anondb.clear_partner(partner)

    await message.reply_text(
        "❌ Chat ended"
    )

    await client.send_message(
        partner,
        "❌ Partner disconnected"
    )

# ---------------- RELAY ---------------- #

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

    try:
        await message.copy(partner)
    except:
        pass
