import asyncio
from pyrogram import Client, filters
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from yt_dlp import YoutubeDL
from config import API_ID, API_HASH, BOT_TOKEN

app = Client(
    "MusicBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

pytgcalls = PyTgCalls(app)

queues = {}

ydl_opts = {
    "format": "bestaudio",
    "quiet": True,
    "outtmpl": "downloads/%(id)s.%(ext)s"
}

def download_song(query):
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{query}", download=True)["entries"][0]
        return info["url"], info["title"]

@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply(
        "🎵 **Pro Music Bot Ready**\n\n"
        "/play song_name\n"
        "/skip\n"
        "/stop"
    )

@app.on_message(filters.command("play") & filters.group)
async def play(_, message):
    chat_id = message.chat.id
    query = " ".join(message.command[1:])
    if not query:
        return await message.reply("❌ Song ka naam likh bhai")

    msg = await message.reply("🔎 Search kar raha hoon...")
    url, title = download_song(query)

    if chat_id not in queues:
        queues[chat_id] = []

    queues[chat_id].append((url, title))

    if len(queues[chat_id]) == 1:
        await pytgcalls.join_group_call(
            chat_id,
            AudioPiped(url),
        )
        await msg.edit(f"▶️ **Now Playing:** {title}")
    else:
        await msg.edit(f"➕ **Queue me add:** {title}")

@app.on_message(filters.command("skip") & filters.group)
async def skip(_, message):
    chat_id = message.chat.id

    if chat_id not in queues or len(queues[chat_id]) == 0:
        return await message.reply("❌ Queue empty hai")

    queues[chat_id].pop(0)

    if len(queues[chat_id]) == 0:
        await pytgcalls.leave_group_call(chat_id)
        await message.reply("⏹ Music stop")
    else:
        url, title = queues[chat_id][0]
        await pytgcalls.change_stream(
            chat_id,
            AudioPiped(url)
        )
        await message.reply(f"⏭ **Skipped**\n▶️ {title}")

@app.on_message(filters.command("stop") & filters.group)
async def stop(_, message):
    chat_id = message.chat.id
    queues.pop(chat_id, None)
    await pytgcalls.leave_group_call(chat_id)
    await message.reply("⏹ Music stopped")

@app.on_message(filters.command("join"))
async def join(_, message):
    await pytgcalls.start()

app.start()
pytgcalls.start()
asyncio.get_event_loop().run_forever()
