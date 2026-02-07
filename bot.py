import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types import Update
from pytgcalls.types.groups import GroupCallParticipantsUpdate
from yt_dlp import YoutubeDL
from pymongo import MongoClient
import re

from config import API_ID, API_HASH, BOT_TOKEN, MONGO_URL

# ────────── MongoDB ──────────
mongo = MongoClient(mongodb+srv://littichhokhabhnkichu_db_user:agPdfLn5VaaoOzW5@cluster0.cqapsq3.mongodb.net/?appName=Cluster0)
db = mongo.musicbot
settings = db.settings

def get_setting(chat_id, key, default=True):
    data = settings.find_one({"chat_id": chat_id})
    return data.get(key, default) if data else default

def set_setting(chat_id, key, value):
    settings.update_one(
        {"chat_id": chat_id},
        {"$set": {key: value}},
        upsert=True
    )

# ────────── Bot ──────────
app = Client(
    "MusicBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)
pytgcalls = PyTgCalls(app)

queues = {}

# ────────── YouTube ──────────
ydl_opts = {
    "format": "bestaudio",
    "quiet": True
}

def yt_search(query):
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{query}", download=False)["entries"][0]
        return info["url"], info["title"], info["duration"], info["thumbnail"]

# ────────── Spotify → YouTube ──────────
def spotify_to_query(url):
    # Spotify title fetch via oEmbed (simple + safe)
    import requests
    data = requests.get(
        "https://open.spotify.com/oembed",
        params={"url": url}
    ).json()
    return f"{data['title']} {data['author_name']}"

# ────────── Utils ──────────
def format_time(sec):
    m, s = divmod(sec, 60)
    return f"{m}:{s:02d}"

def buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏸ Pause", callback_data="pause"),
            InlineKeyboardButton("▶️ Resume", callback_data="resume")
        ],
        [
            InlineKeyboardButton("⏭ Skip", callback_data="skip"),
            InlineKeyboardButton("⏹ Stop", callback_data="stop")
        ],
        [
            InlineKeyboardButton("📜 Queue", callback_data="queue")
        ]
    ])

async def is_admin(client, chat_id, user_id):
    admins = await client.get_chat_members(chat_id, filter="administrators")
    return user_id in [a.user.id for a in admins]

# ────────── Commands ──────────
@app.on_message(filters.command("play") & filters.group)
async def play(_, message):
    chat_id = message.chat.id
    query = " ".join(message.command[1:])
    if not query:
        return await message.reply("❌ Song ya Spotify link de bhai")

    if "spotify.com" in query:
        query = spotify_to_query(query)

    msg = await message.reply("🔎 Search ho raha hai...")
    url, title, duration, thumb = yt_search(query)

    queues.setdefault(chat_id, []).append((url, title, duration, thumb))

    if len(queues[chat_id]) == 1:
        await pytgcalls.join_group_call(chat_id, AudioPiped(url))
        await app.send_photo(
            chat_id,
            photo=thumb,
            caption=f"🎵 **Now Playing**\n📌 {title}\n⏱ {format_time(duration)}",
            reply_markup=buttons()
        )
    else:
        await msg.edit(f"➕ Queue me add: **{title}**")

# ────────── Callbacks ──────────
@app.on_callback_query()
async def cb(_, q: CallbackQuery):
    chat_id = q.message.chat.id
    user_id = q.from_user.id

    if get_setting(chat_id, "admin_only", True):
        if not await is_admin(app, chat_id, user_id):
            return await q.answer("❌ Sirf admin", show_alert=True)

    if q.data == "pause":
        await pytgcalls.pause_stream(chat_id)
        await q.answer("⏸ Paused")

    elif q.data == "resume":
        await pytgcalls.resume_stream(chat_id)
        await q.answer("▶️ Resumed")

    elif q.data == "skip":
        queues[chat_id].pop(0)
        if queues[chat_id]:
            await pytgcalls.change_stream(
                chat_id, AudioPiped(queues[chat_id][0][0])
            )
        else:
            await pytgcalls.leave_group_call(chat_id)
        await q.answer("⏭ Skipped")

    elif q.data == "stop":
        queues.pop(chat_id, None)
        await pytgcalls.leave_group_call(chat_id)
        await q.answer("⏹ Stopped")

    elif q.data == "queue":
        if not queues.get(chat_id):
            return await q.answer("Queue empty", show_alert=True)
        text = "\n".join(
            f"{i+1}. {s[1]}" for i, s in enumerate(queues[chat_id])
        )
        await q.message.reply(f"📜 **Queue**\n{text}")

# ────────── Auto Leave ──────────
@pytgcalls.on_update()
async def auto_leave(update: Update):
    if isinstance(update, GroupCallParticipantsUpdate):
        if len(update.participants) <= 1:
            queues.pop(update.chat_id, None)
            await pytgcalls.leave_group_call(update.chat_id)

# ────────── Start ──────────
app.start()
pytgcalls.start()
asyncio.get_event_loop().run_forever()
