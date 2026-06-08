import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, UserIsBlocked

from pyrogram.raw.functions.messages import SetTyping
from pyrogram.raw.types import SendMessageTypingAction

from database.anondb import anondb

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

# ---------------- TYPING ---------------- #

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

# ---------------- PROFILE COMMAND ---------------- #

@Client.on_message(filters.private & filters.command("profile"))
async def profile_cmd(client, message):

    user_id = message.from_user.id

    await anondb.create_user(user_id)
    user = await anondb.get_user(user_id)

    if user.get("profile", {}).get("name"):
        return await message.reply_text("Your profile is already completed.")

    profile_states[user_id] = "name"
    profile_data[user_id] = {}

    await message.reply_text("Send your name:")


# ---------------- PROFILE HANDLER ---------------- #

@Client.on_message(filters.private, group=1)
async def profile_handler(client, message):

    user_id = message.from_user.id

    if user_id not in profile_states:
        return

    if message.text and message.text.startswith("/"):
        return

    if not message.text:
        return await message.reply_text("Please send text only.")

    text = message.text.strip()
    step = profile_states[user_id]

    if step == "name":
        profile_data[user_id]["name"] = text
        profile_states[user_id] = "age"
        return await message.reply_text("Send your age:")

    elif step == "age":

        if not text.isdigit():
            return await message.reply_text("Send valid age.")

        age = int(text)

        if age < 10 or age > 99:
            return await message.reply_text("Age must be between 10 - 99.")

        profile_data[user_id]["age"] = age
        profile_states[user_id] = "gender"

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Male", callback_data="gender_male"),
                InlineKeyboardButton("Female", callback_data="gender_female")
            ],
            [
                InlineKeyboardButton("Other", callback_data="gender_other")
            ]
        ])

        return await message.reply_text("Select gender:", reply_markup=buttons)

    elif step == "location":

        profile_data[user_id]["location"] = text

        await anondb.set_profile(user_id, {
            "name": profile_data[user_id]["name"],
            "age": profile_data[user_id]["age"],
            "gender": profile_data[user_id]["gender"],
            "location": profile_data[user_id]["location"]
        })

        profile_states.pop(user_id, None)
        profile_data.pop(user_id, None)

        return await message.reply_text(
            "Profile completed.\n\nUse /chat to find partner."
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

    await query.answer(f"{gender.capitalize()} selected")
    await query.message.reply_text("Send your location:")


# ---------------- MY PROFILE ---------------- #

@Client.on_message(filters.private & filters.command("myprofile"))
async def myprofile(client, message):

    user_id = message.from_user.id
    user = await anondb.get_user(user_id)

    if not user.get("profile", {}).get("name"):
        return await message.reply_text("You have not created profile yet.\nUse /profile")

    p = user["profile"]

    text = f"""
Your Profile

Name : {p.get('name')}
Age : {p.get('age')}
Gender : {p.get('gender')}
Location : {p.get('location')}
"""

    await message.reply_text(text)


# ---------------- CHAT ---------------- #

@Client.on_message(filters.private & filters.command("chat"))
async def search_partner(client, message):

    user_id = message.from_user.id
    user = await anondb.get_user(user_id)

    if not user.get("profile", {}).get("name"):
        return await message.reply_text("Complete profile first using /profile")

    async with waiting_lock:

        if user_id in sessions:
            return await message.reply_text("You are already connected.")

        if user_id in waiting_users:
            return await message.reply_text("Already searching for partner...")

        waiting_users.add(user_id)

        search_msg = await message.reply_text("Searching for partner...")

        async def timeout_task():
            await asyncio.sleep(SEARCH_TIMEOUT)
            if user_id in waiting_users:
                waiting_users.discard(user_id)
                try:
                    await search_msg.edit_text("No partner found.\nTry again later.")
                except:
                    pass

        search_tasks[user_id] = asyncio.create_task(timeout_task())

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

            text1 = f"""
Partner connected

Name : {u2['profile']['name']}
Age : {u2['profile']['age']}
Gender : {u2['profile']['gender']}
Location : {u2['profile']['location']}
"""

            text2 = f"""
Partner connected

Name : {u1['profile']['name']}
Age : {u1['profile']['age']}
Gender : {u1['profile']['gender']}
Location : {u1['profile']['location']}
"""

            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Next", callback_data="anon_next"),
                    InlineKeyboardButton("End", callback_data="anon_end")
                ]
            ])

            await client.send_message(user1, text1, reply_markup=buttons)
            await client.send_message(user2, text2, reply_markup=buttons)


# ---------------- RELAY (🔥 TYPING ADDED) ---------------- #

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
        # 🔥 TYPING EFFECT
        await send_typing(client, partner)

        await asyncio.sleep(1)

        await message.copy(partner)

    except FloodWait as e:
        await asyncio.sleep(e.value)

    except UserIsBlocked:
        sessions.pop(user_id, None)
        sessions.pop(partner, None)

    except Exception as e:
        print("[RELAY ERROR]", e)
