# plugins/anonymous.py

import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, UserIsBlocked

from database.users import db

# ---------------- CONFIG ---------------- #

SEARCH_TIMEOUT = 120
IDLE_CHAT_LIMIT = 1800

# ---------------- GLOBALS ---------------- #

waiting_users = set()
sessions = {}
chat_timers = {}
search_tasks = {}

profile_states = {}
profile_data = {}

waiting_lock = asyncio.Lock()

# ---------------- START ---------------- #

START_TEXT = """
Anonymous Chat Feature

You can chat anonymously with random users.

Commands:

/search - Find partner
/next - Next partner
/end - End chat
/profile - Create profile
/myprofile - View profile
"""

# ---------------- PROFILE COMMAND ---------------- #

@Client.on_message(filters.private & filters.command("profile"))
async def profile_cmd(client, message):

    user_id = message.from_user.id

    user = await db.get_user(user_id)

    profile = user.get("profile", {}) if user else {}

    if profile.get("name"):
        return await message.reply_text(
            "✅ Your profile is already completed."
        )

    profile_states[user_id] = "name"
    profile_data[user_id] = {}

    await message.reply_text(
        "Send your name:"
    )

# ---------------- PROFILE HANDLER ---------------- #

@Client.on_message(filters.private, group=1)
async def profile_handler(client, message):

    user_id = message.from_user.id

    if user_id not in profile_states:
        return

    if message.text and message.text.startswith("/"):
        return

    if not message.text:
        return await message.reply_text(
            "Please send text only."
        )

    text = message.text.strip()

    step = profile_states[user_id]

    # ---------- NAME ---------- #

    if step == "name":

        profile_data[user_id]["name"] = text

        profile_states[user_id] = "age"

        await message.reply_text(
            "Send your age:"
        )

    # ---------- AGE ---------- #

    elif step == "age":

        if not text.isdigit():
            return await message.reply_text(
                "Send valid age."
            )

        age = int(text)

        if age < 10 or age > 99:
            return await message.reply_text(
                "Age must be between 10 - 99."
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

        await message.reply_text(
            "Select gender:",
            reply_markup=buttons
        )

    # ---------- LOCATION ---------- #

    elif step == "location":

        profile_data[user_id]["location"] = text

        user = await db.get_user(user_id)

        profile = user.get("profile", {}) if user else {}

        profile.update(profile_data[user_id])

        await db.add_user(
            user_id,
            profile,
            user_type="user"
        )

        profile_states.pop(user_id, None)
        profile_data.pop(user_id, None)

        await message.reply_text(
            "✅ Profile completed.\n\nUse /search to find partner."
        )

# ---------------- GENDER CALLBACK ---------------- #

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
        "Send your location:"
    )

# ---------------- MY PROFILE ---------------- #

@Client.on_message(filters.private & filters.command("myprofile"))
async def myprofile(client, message):

    user_id = message.from_user.id

    user = await db.get_user(user_id)

    profile = user.get("profile", {}) if user else {}

    if not profile.get("name"):
        return await message.reply_text(
            "You have not created profile yet.\nUse /profile"
        )

    text = f"""
Your Profile

Name : {profile.get('name')}
Age : {profile.get('age')}
Gender : {profile.get('gender')}
Location : {profile.get('location')}
"""

    await message.reply_text(text)

# ---------------- START ---------------- #

@Client.on_message(filters.private & filters.command("start"))
async def start(client, message):

    user_id = message.from_user.id

    user = await db.get_user(user_id)

    if not user:
        await db.add_user(
            user_id,
            {
                "name": "",
                "age": "",
                "gender": "",
                "location": ""
            },
            user_type="user"
        )

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "Start Anonymous Chat",
                callback_data="start_anon"
            )
        ]
    ])

    await message.reply_text(
        START_TEXT,
        reply_markup=buttons
    )

# ---------------- START BUTTON ---------------- #

@Client.on_callback_query(filters.regex("^start_anon$"))
async def start_anon(client, query):

    user_id = query.from_user.id

    user = await db.get_user(user_id)

    profile = user.get("profile", {}) if user else {}

    if not profile.get("name"):

        return await query.message.reply_text(
            "Please create your profile first using /profile"
        )

    await query.message.reply_text(
        "Use /search to find a partner."
    )

# ---------------- SEARCH ---------------- #

@Client.on_message(filters.private & filters.command("search"))
async def search_partner(client, message):

    user_id = message.from_user.id

    user = await db.get_user(user_id)

    profile = user.get("profile", {}) if user else {}

    if not profile.get("name"):
        return await message.reply_text(
            "Complete profile first using /profile"
        )

    async with waiting_lock:

        if user_id in sessions:
            return await message.reply_text(
                "You are already connected."
            )

        if user_id in waiting_users:
            return await message.reply_text(
                "Already searching for partner..."
            )

        waiting_users.add(user_id)

        search_msg = await message.reply_text(
            "Searching for partner..."
        )

        # ---------- SEARCH TIMEOUT ---------- #

        async def timeout_task():

            await asyncio.sleep(SEARCH_TIMEOUT)

            if user_id in waiting_users:

                waiting_users.discard(user_id)

                try:
                    await search_msg.edit_text(
                        "No partner found.\nTry again later."
                    )
                except Exception:
                    pass

        search_tasks[user_id] = asyncio.create_task(
            timeout_task()
        )

        # ---------- PAIR USERS ---------- #

        if len(waiting_users) >= 2:

            user1 = waiting_users.pop()
            user2 = waiting_users.pop()

            if user1 == user2:
                waiting_users.add(user1)
                return

            # cancel timeout

            if user1 in search_tasks:
                search_tasks[user1].cancel()

            if user2 in search_tasks:
                search_tasks[user2].cancel()

            sessions[user1] = user2
            sessions[user2] = user1

            chat_timers[user1] = datetime.utcnow()
            chat_timers[user2] = datetime.utcnow()

            try:
                await db.set_partners_atomic(user1, user2)
            except Exception:
                pass

            u1 = await db.get_user(user1)
            u2 = await db.get_user(user2)

            p1 = u1.get("profile", {})
            p2 = u2.get("profile", {})

            text1 = f"""
Partner connected

Name : {p2.get('name')}
Age : {p2.get('age')}
Gender : {p2.get('gender')}
Location : {p2.get('location')}
"""

            text2 = f"""
Partner connected

Name : {p1.get('name')}
Age : {p1.get('age')}
Gender : {p1.get('gender')}
Location : {p1.get('location')}
"""

            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "Next",
                        callback_data="anon_next"
                    ),
                    InlineKeyboardButton(
                        "End",
                        callback_data="anon_end"
                    )
                ]
            ])

            try:
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

            except Exception as e:

                print(f"[SEARCH ERROR] {e}")

# ---------------- NEXT CALLBACK ---------------- #

@Client.on_callback_query(filters.regex("^anon_next$"))
async def next_callback(client, query):

    user_id = query.from_user.id

    partner = sessions.pop(user_id, None)

    if not partner:

        return await query.message.reply_text(
            "You are not connected."
        )

    sessions.pop(partner, None)

    chat_timers.pop(user_id, None)
    chat_timers.pop(partner, None)

    try:
        await db.reset_partners(user_id, partner)
    except Exception:
        pass

    try:
        await client.send_message(
            partner,
            "Partner disconnected."
        )
    except Exception:
        pass

    await client.send_message(
        user_id,
        "Searching next partner..."
    )

    fake_message = query.message
    fake_message.from_user = query.from_user

    await search_partner(client, fake_message)

# ---------------- END CALLBACK ---------------- #

@Client.on_callback_query(filters.regex("^anon_end$"))
async def end_callback(client, query):

    user_id = query.from_user.id

    partner = sessions.pop(user_id, None)

    if not partner:

        return await query.message.reply_text(
            "You are not connected."
        )

    sessions.pop(partner, None)

    chat_timers.pop(user_id, None)
    chat_timers.pop(partner, None)

    try:
        await db.reset_partners(user_id, partner)
    except Exception:
        pass

    await client.send_message(
        user_id,
        "Chat ended."
    )

    try:
        await client.send_message(
            partner,
            "Partner ended the chat."
        )
    except Exception:
        pass

# ---------------- NEXT COMMAND ---------------- #

@Client.on_message(filters.private & filters.command("next"))
async def next_command(client, message):

    user_id = message.from_user.id

    partner = sessions.pop(user_id, None)

    if not partner:
        return await message.reply_text(
            "You are not connected."
        )

    sessions.pop(partner, None)

    chat_timers.pop(user_id, None)
    chat_timers.pop(partner, None)

    try:
        await db.reset_partners(user_id, partner)
    except Exception:
        pass

    try:
        await client.send_message(
            partner,
            "Partner disconnected."
        )
    except Exception:
        pass

    await message.reply_text(
        "Searching next partner..."
    )

    await search_partner(client, message)

# ---------------- END COMMAND ---------------- #

@Client.on_message(filters.private & filters.command("end"))
async def end_chat(client, message):

    user_id = message.from_user.id

    partner = sessions.pop(user_id, None)

    if not partner:
        return await message.reply_text(
            "You are not connected."
        )

    sessions.pop(partner, None)

    chat_timers.pop(user_id, None)
    chat_timers.pop(partner, None)

    try:
        await db.reset_partners(user_id, partner)
    except Exception:
        pass

    await message.reply_text(
        "Chat ended."
    )

    try:
        await client.send_message(
            partner,
            "Partner ended the chat."
        )
    except Exception:
        pass

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

    chat_timers[user_id] = datetime.utcnow()
    chat_timers[partner] = datetime.utcnow()

    try:
        await message.copy(partner)

    except FloodWait as e:

        await asyncio.sleep(e.value)

    except UserIsBlocked:

        sessions.pop(user_id, None)
        sessions.pop(partner, None)

    except Exception as e:

        print(f"[RELAY ERROR] {e}")

# ---------------- IDLE CHECKER ---------------- #

async def idle_checker(client):

    while True:

        now = datetime.utcnow()

        for user_id, last_active in list(chat_timers.items()):

            try:

                seconds = (
                    now - last_active
                ).total_seconds()

                if seconds > IDLE_CHAT_LIMIT:

                    partner = sessions.get(user_id)

                    if partner:

                        try:
                            await client.send_message(
                                user_id,
                                "Chat ended due to inactivity."
                            )

                            await client.send_message(
                                partner,
                                "Chat ended due to inactivity."
                            )

                        except Exception:
                            pass

                        sessions.pop(user_id, None)
                        sessions.pop(partner, None)

                        chat_timers.pop(user_id, None)
                        chat_timers.pop(partner, None)

                        try:
                            await db.reset_partners(
                                user_id,
                                partner
                            )
                        except Exception:
                            pass

            except Exception as e:
                print(f"[IDLE ERROR] {e}")

        await asyncio.sleep(60)
