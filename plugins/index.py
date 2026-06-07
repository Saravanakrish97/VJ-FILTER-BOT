# Don't Remove Credit @TamilBots
# Subscribe YouTube Channel For Amazing Bot @Tamilbots
# Ask Doubt on telegram @TamilSupport

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

    if int(from_user) not in ADMINS:
        await bot.send_message(
            int(from_user),
            f'Your Submission for indexing {chat} has been accepted.',
            reply_to_message_id=int(lst_msg_id)
        )

    await msg.edit(
        "Starting Indexing",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
        )
    )

    try:
        chat = int(chat)
    except:
        pass

    await index_files_to_db(int(lst_msg_id), chat, msg, bot)


@Client.on_message(filters.private & filters.command('index'))
async def send_for_index(bot, message):

    ask = await bot.ask(
        message.chat.id,
        "**Send channel last post link OR forward last message from channel**"
    )

    chat_id = None
    last_msg_id = None

    # LINK METHOD
    if ask.text:

        regex = re.compile(
            r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$"
        )

        match = regex.match(ask.text)

        if not match:
            return await ask.reply(
                "Invalid link\n\nTry again using /index"
            )

        chat_id = match.group(4)
        last_msg_id = int(match.group(5))

        if str(chat_id).isnumeric():
            chat_id = int("-100" + str(chat_id))

    # FORWARDED MESSAGE METHOD
    elif ask.forward_from_chat:

        if ask.forward_from_chat.type != enums.ChatType.CHANNEL:
            return await ask.reply("Forward message must be from channel.")

        last_msg_id = ask.forward_from_message_id

        chat_id = (
            ask.forward_from_chat.username
            or ask.forward_from_chat.id
        )

    else:
        return await ask.reply("Invalid input.")

    # CHECK CHAT
    try:
        await bot.get_chat(chat_id)

    except ChannelInvalid:
        return await ask.reply(
            'Private channel/group detected.\n'
            'Make me admin there.'
        )

    except (UsernameInvalid, UsernameNotModified):
        return await ask.reply('Invalid link specified.')

    except Exception as e:
        logger.exception(e)
        return await ask.reply(f'Error:\n{e}')

    # CHECK LAST MESSAGE
    try:
        k = await bot.get_messages(chat_id, last_msg_id)

    except Exception as e:
        return await ask.reply(
            'Make sure I am admin in the channel.\n\n'
            f'Error: {e}'
        )

    if not k:
        return await ask.reply("Message not found.")

    # ADMIN DIRECT INDEX
    if message.from_user.id in ADMINS:

        buttons = [[
            InlineKeyboardButton(
                'Yes',
                callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}'
            )
        ],
        [
            InlineKeyboardButton(
                'Close',
                callback_data='close_data'
            )
        ]]

        return await message.reply(
            f'Do you want to index this?\n\n'
            f'Chat: <code>{chat_id}</code>\n'
            f'Last Msg ID: <code>{last_msg_id}</code>',
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # NORMAL USER REQUEST
    if isinstance(chat_id, int):

        try:
            link = (
                await bot.create_chat_invite_link(chat_id)
            ).invite_link

        except ChatAdminRequired:
            return await message.reply(
                'Make me admin with invite permission.'
            )

    else:
        link = f"https://t.me/{chat_id}"

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
        f'By : {message.from_user.mention} '
        f'(<code>{message.from_user.id}</code>)\n\n'
        f'Chat : <code>{chat_id}</code>\n'
        f'Last Msg ID : <code>{last_msg_id}</code>\n'
        f'Invite : {link}',
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    await message.reply(
        'Thank you.\nWait for moderators approval.'
    )


@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):

    if len(message.command) < 2:
        return await message.reply("Give skip number")

    try:
        skip = int(message.command[1])

    except:
        return await message.reply(
            "Skip number should be integer."
        )

    temp.CURRENT = skip

    await message.reply(
        f"Successfully set SKIP number as {skip}"
    )


async def index_files_to_db(lst_msg_id, chat, msg, bot):

    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0

    async with lock:

        try:

            current = temp.CURRENT
            temp.CANCEL = False

            async for message in bot.iter_messages(
                chat,
                lst_msg_id,
                temp.CURRENT
            ):

                if temp.CANCEL:

                    return await msg.edit(
                        f"Cancelled\n\n"
                        f"Saved: <code>{total_files}</code>\n"
                        f"Duplicate: <code>{duplicate}</code>\n"
                        f"Deleted: <code>{deleted}</code>\n"
                        f"No Media: <code>{no_media}</code>\n"
                        f"Unsupported: <code>{unsupported}</code>\n"
                        f"Errors: <code>{errors}</code>"
                    )

                current += 1

                if current % 60 == 0:

                    await asyncio.sleep(2)

                    await msg.edit_text(
                        text=(
                            f"Fetched: <code>{current}</code>\n"
                            f"Saved: <code>{total_files}</code>\n"
                            f"Duplicate: <code>{duplicate}</code>\n"
                            f"Deleted: <code>{deleted}</code>\n"
                            f"No Media: <code>{no_media}</code>\n"
                            f"Unsupported: <code>{unsupported}</code>\n"
                            f"Errors: <code>{errors}</code>"
                        ),
                        reply_markup=InlineKeyboardMarkup(
                            [[
                                InlineKeyboardButton(
                                    'Cancel',
                                    callback_data='index_cancel'
                                )
                            ]]
                        )
                    )

                if message.empty:
                    deleted += 1
                    continue

                if not message.media:
                    no_media += 1
                    continue

                if message.media not in [
                    enums.MessageMediaType.VIDEO,
                    enums.MessageMediaType.AUDIO,
                    enums.MessageMediaType.DOCUMENT
                ]:
                    unsupported += 1
                    continue

                media = getattr(
                    message,
                    message.media.value,
                    None
                )

                if not media:
                    unsupported += 1
                    continue

                media.file_type = message.media.value
                media.caption = message.caption

                saved, result = await save_file(media)

                if saved:
                    total_files += 1

                elif result == 0:
                    duplicate += 1

                elif result == 2:
                    errors += 1

        except FloodWait as e:
            await asyncio.sleep(e.value)

        except Exception as e:
            logger.exception(e)

            await msg.edit(f'Error:\n<code>{e}</code>')

        else:

            await msg.edit(
                f'Successfully saved '
                f'<code>{total_files}</code> files!\n\n'
                f'Duplicate: <code>{duplicate}</code>\n'
                f'Deleted: <code>{deleted}</code>\n'
                f'No Media: <code>{no_media}</code>\n'
                f'Unsupported: <code>{unsupported}</code>\n'
                f'Errors: <code>{errors}</code>'
            )
