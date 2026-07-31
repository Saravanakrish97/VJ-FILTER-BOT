from pyrogram import Client, filters
from pyrogram.types import Message
import re
import asyncio

TNEB_USERS = {}

@Client.on_message(filters.private & filters.command("tneb"))
async def tneb_start(client, message: Message):
    TNEB_USERS[message.from_user.id] = {"step": "name"}
    await message.reply("Enter name (format: `ramesh.g`):")

@Client.on_message(filters.private & filters.text)
async def tneb_flow(client, message: Message):
    uid = message.from_user.id
    
    if uid not in TNEB_USERS:
        return
    if message.text.startswith("/"):
        return
    
    data = TNEB_USERS[uid]
    
    if data["step"] == "name":
        name = message.text.strip().lower()
        
        if not re.match(r"^[a-z]+\.[a-z]$", name):
            return await message.reply("Invalid! Use: `ramesh.g`")
        
        data["name"] = name
        data["step"] = "emp"
        return await message.reply("Enter Employee Code:")
    
    if data["step"] == "emp":
        emp = message.text.strip()
        
        if not emp.isdigit():
            return await message.reply("Numbers only!")
        
        name = data["name"]
        password = name[:2] + emp
        
        total = 10
        msg = await message.reply("🔍 Searching...")
        
        for i in range(total):
            username = name if i == 0 else f"{name}{i}"
            
            # Simple dots animation
            dots = "●" * (i + 1) + "○" * (total - i - 1)
            percent = int(((i + 1) / total) * 100)
            
            text = f"🔍 Checking: `{username}`\n\n{dots} {percent}%"
            
            # Every 5 checks, add update
            if (i + 1) % 5 == 0:
                text += f"\n\n✅ {i + 1} checked..."
            
            await msg.edit_text(text)
            await asyncio.sleep(1)
            
            # Demo success at 7th
            if i == 6:
                success = username
                break
        else:
            success = None
        
        del TNEB_USERS[uid]
        
        if success:
            await msg.edit_text(
                f"✅ Success!\n\n"
                f"Username: `{success}`\n"
                f"Password: `{password}`"
            )
        else:
            await msg.edit_text("❌ Not found")
