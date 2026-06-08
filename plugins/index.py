import logging
import asyncio
import re

from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import (
    ChannelInvalid,
    ChatAdminRequired,
    UsernameInvalid,
    UsernameNotModified
)
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import ADMINS
from info import INDEX_REQ_CHANNEL as LOG_CHANNEL
from database.ia_filterdb import save_file
from utils import temp

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

lock = asyncio.Lock()


# ---------------------------
# SAFE EDIT HELPER (FIX)
# ---------------------------
async def safe_edit(bot, msg, text, reply_markup=None):
    try:
        return await bot.edit_message_text(
            chat_id=msg.chat.id,
            message_id=msg.id,
            text=text,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.warning(f"Edit failed: {e}")
        return None


# ---------------------------
# CALLBACK INDEX HANDLER
# ---------------------------
@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):

    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        return await query.answer("Cancelling Indexing")

    _, raju, chat, lst_msg_id, from_user = query.data.split("#")

    if raju == 'reject':
        await query.message.delete()

        await bot.send_message(
            int(from_user),
            f'Your Submission for indexing {chat} has been declined by moderators.',
            reply_to_message_id=int(lst_msg_id)
        )
        return

    if lock.locked():
        return await query.answer(
            'Wait until previous process complete.',
            show_alert=True
        )

    msg = query.message
    await query.answer('Processing...⏳', show_alert=True)

    try:
        await safe_edit(
            bot,
            msg,
            "Starting Indexing...",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
            )
        )
    except Exception:
        pass

    try:
        chat = int(chat)
    except:
        pass

    await index_files_to_db(int(lst_msg_id), chat, msg, bot)


# ---------------------------
# USER INDEX REQUEST
# ---------------------------
@Client.on_message(filters.private & filters.command('index'))
async def send_for_index(bot, message):

    ask = await bot.ask(
        message.chat.id,
        "**Send channel last post link OR forward last message from channel**"
    )

    chat_id = None
    last_msg_id = None

    if ask.text:

        regex = re.compile(
            r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$"
        )

        match = regex.match(ask.text)

        if not match:
            return await ask.reply("Invalid link\n\nTry again using /index")

        chat_id = match.group(4)
        last_msg_id = int(match.group(5))

        if str(chat_id).isnumeric():
            chat_id = int("-100" + str(chat_id))

    elif ask.forward_from_chat:

        if ask.forward_from_chat.type != enums.ChatType.CHANNEL:
            return await ask.reply("Forward message must be from channel.")

        last_msg_id = ask.forward_from_message_id
        chat_id = ask.forward_from_chat.username or ask.forward_from_chat.id

    else:
        return await ask.reply("Invalid input.")

    try:
        await bot.get_chat(chat_id)
    except Exception as e:
        return await ask.reply(f'Error: {e}')

    try:
        await bot.get_messages(chat_id, last_msg_id)
    except Exception as e:
        return await ask.reply(f'Make sure bot has access.\nError: {e}')

    buttons = [
        [
            InlineKeyboardButton(
                'Accept Index',
                callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}'
            )
        ],
        [
            InlineKeyboardButton(
                'Reject Index',
                callback_data=f'index#reject#{chat_id}#{message.id}#{message.from_user.id}'
            )
        ]
    ]

    await bot.send_message(
        LOG_CHANNEL,
        f'#IndexRequest\n\n'
        f'By : {message.from_user.mention}\n'
        f'Chat : <code>{chat_id}</code>\n'
        f'Last Msg ID : <code>{last_msg_id}</code>',
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    await message.reply("Thank you. Wait for approval.")


# ---------------------------
# SKIP SET
# ---------------------------
@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):

    if len(message.command) < 2:
        return await message.reply("Give skip number")

    try:
        skip = int(message.command[1])
    except:
        return await message.reply("Skip must be integer")

    temp.CURRENT = skip

    await message.reply(f"Skip set to {skip}")


# ---------------------------
# MAIN INDEXER
# ---------------------------
async def index_files_to_db(lst_msg_id, chat, msg, bot):

    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0

    async with lock:

        temp.CANCEL = False
        current = temp.CURRENT

        try:

            while current <= lst_msg_id:

                if temp.CANCEL:
                    return await safe_edit(
                        bot, msg,
                        f"Cancelled\nSaved: {total_files}\nDuplicate: {duplicate}\nDeleted: {deleted}"
                    )

                try:
                    messages = await bot.get_messages(chat, list(range(current, current + 200)))
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    continue
                except Exception as e:
                    logger.error(e)
                    current += 200
                    continue

                for message in messages:

                    if temp.CANCEL:
                        break

                    if not message or message.empty:
                        deleted += 1
                        continue

                    media = (
                        message.video or
                        message.audio or
                        message.document or
                        message.photo or
                        message.animation
                    )

                    if not media:
                        no_media += 1
                        continue

                    try:
                        saved, result = await save_file(media)

                        if saved:
                            total_files += 1
                        elif result == 0:
                            duplicate += 1
                        else:
                            errors += 1

                    except Exception as e:
                        logger.error(e)
                        errors += 1

                current += 200
                temp.CURRENT = current

                # SAFE progress update
                if current % 1000 == 0:
                    await safe_edit(
                        bot,
                        msg,
                        f"Indexing...\nFetched: {current}\nSaved: {total_files}\nDeleted: {deleted}"
                    )

            await safe_edit(
                bot,
                msg,
                f"Completed\nSaved: {total_files}\nDuplicate: {duplicate}\nDeleted: {deleted}\nNoMedia: {no_media}"
            )

        except Exception as e:
            logger.exception(e)
            await safe_edit(bot, msg, f"Error:\n{e}")
