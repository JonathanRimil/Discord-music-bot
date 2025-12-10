import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import yt_dlp
from collections import defaultdict, deque
import json
from pathlib import Path
import re
import asyncio


# -------------------------------
# PROFANITY FILTER (SMART REGEX)
# -------------------------------
profanity_patterns = [
    r"\bshit\b",
    r"s[h\*\.\_ ]*i[t\*\.\_ ]*",
    r"f[u\*\.\_ ]*c[k\*\.\_ ]*",
    r"\bass[h\*\.\_ ]*o[l\*\.\_ ]*e\b",
    r"\bb[i1]tch\b",
    r"\bcu[n\*\.\_ ]*t\b",
    r"\bn[i1]gg[aer]+\b",
    r"\bwhore\b",
    r"\bslut\b",
    r"\bdumbass\b",
]
compiled_profanity = [re.compile(p, re.IGNORECASE) for p in profanity_patterns]

# -------------------------------
# PLAYLIST STORAGE
# -------------------------------
DATA_DIR = Path("data/playlists")
DATA_DIR.mkdir(parents=True, exist_ok=True)

def get_user_dir(user_id):
    folder = DATA_DIR / str(user_id)
    folder.mkdir(exist_ok=True)
    return folder

def get_playlist_file(user_id, name):
    return get_user_dir(user_id) / f"{name.lower()}.json"

# -------------------------------
# MUSIC PLAYER CLASS
# -------------------------------
class MusicPlayer:
    def __init__(self, guild):
        self.guild = guild
        self.queue = deque()
        self.autoplay = True
        self.last_song_id = None

    async def play_next(self, ctx):
        if not self.queue:
            if self.autoplay and self.last_song_id:
                await self.play_related(ctx)
            return

        song = self.queue.popleft()
        self.last_song_id = song.get("id")

        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn"
        }

        source = await discord.FFmpegOpusAudio.from_probe(song["url"], **ffmpeg_options)
        await send_now_playing(ctx, song)

        ctx.voice_client.play(
            source,
            after=lambda e: bot.loop.create_task(self.play_next(ctx))
        )

    async def play_related(self, ctx):
        """Autoplay next related video when queue ends"""
        if not self.last_song_id:
            return

        ydl_opts = {"quiet": True, "extract_flat": "in_playlist"}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            data = ydl.extract_info(f"https://www.youtube.com/watch?v={self.last_song_id}", download=False)

        if "related" in data and data["related"]:
            r = data["related"][0]
            song = {
                "title": r.get("title", "Unknown Title"),
                "url": r["url"],
                "webpage_url": f"https://www.youtube.com/watch?v={r['id']}",
                "id": r["id"]
            }
            self.queue.append(song)
            await ctx.send("🎧 Autoplay added a related song!")
            await self.play_next(ctx)

players = {}

def get_player(guild):
    if guild.id not in players:
        players[guild.id] = MusicPlayer(guild)
    return players[guild.id]

# -------------------------------
# DISCORD SETUP
# -------------------------------
load_dotenv()
token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# -------------------------------
# NOW PLAYING EMBED
# -------------------------------
async def send_now_playing(ctx, song):
    embed = discord.Embed(
        title="🎶 Now Playing",
        description=f"**[{song['title']}]({song['webpage_url']})**",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Requested by {ctx.author.name}")
    await ctx.send(embed=embed)

# -------------------------------
# EVENTS
# -------------------------------
secret_role = "gamer"

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user.name}")

@bot.event
async def on_member_join(member):
    await member.send(f"Welcome to the server, {member.name}!")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    text = message.content.lower()
    for pattern in compiled_profanity:
        if pattern.search(text):
            await message.delete()
            await message.channel.send(
                f"{message.author.mention}, please avoid using inappropriate language."
            )
            return

    await bot.process_commands(message)

# -------------------------------
# HELP MENU
# -------------------------------
@bot.command()
async def helpmenu(ctx):
    embed = discord.Embed(
        title="📘 Bot Help Menu",
        description="Here are all my commands:",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="🎧 Music Commands",
        value=(
            "`!play <song>`\n"
            "`!skip`\n"
            "`!pause`\n"
            "`!resume`\n"
            "`!stop`\n"
            "`!queue`\n"
        ),
        inline=False
    )

    embed.add_field(
        name="📀 Playlist Commands",
        value=(
            "`!saveplaylist <name>`\n"
            "`!loadplaylist <name>`\n"
            "`!myplaylists`\n"
            "`!addtoplaylist <name> <song>`\n"
        ),
        inline=False
    )

    embed.add_field(
        name="🛡 Moderation",
        value="Automatic bad-word filtering",
        inline=False
    )

    embed.add_field(
        name="🔒 Secret Commands",
        value="`!secret` (requires gamer role)",
        inline=False
    )

    await ctx.send(embed=embed)

# -------------------------------
# MUSIC COMMANDS
# -------------------------------
@bot.command()
async def play(ctx, *, query):
    player = get_player(ctx.guild)

    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            return await ctx.send("Join a voice channel first!")

    ydl_opts = {"format": "bestaudio", "quiet": True, "noplaylist": False}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False) if query.startswith("http") \
               else ydl.extract_info(f"ytsearch:{query}", download=False)["entries"][0]

        if "entries" in info:
            for entry in info["entries"]:
                song = {
                    "title": entry.get("title", "Unknown Title"),
                    "url": entry["url"],
                    "webpage_url": entry.get("webpage_url"),
                    "id": entry.get("id")
                }
                player.queue.append(song)
            await ctx.send(f"Added **{len(info['entries'])}** songs!")
        else:
            song = {
                "title": info.get("title", "Unknown Title"),
                "url": info["url"],
                "webpage_url": info.get("webpage_url"),
                "id": info.get("id")
            }
            player.queue.append(song)
            player.last_song_id = info.get("id")

    if not ctx.voice_client.is_playing():
        await player.play_next(ctx)

    await ctx.send("Added to queue! 🎶")

@bot.command()
async def queue(ctx):
    player = get_player(ctx.guild)

    if not player.queue:
        return await ctx.send("Queue is empty.")

    msg = "\n".join([f"{i+1}. {song['title']}" for i, song in enumerate(player.queue)])
    await ctx.send(f"**Current Queue:**\n{msg}")

@bot.command()
async def skip(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        player = get_player(ctx.guild)
        await ctx.send("Skipped! ⏭️")

        await player.play_next(ctx)


@bot.command()
async def pause(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()

@bot.command()
async def resume(ctx):
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()

@bot.command()
async def stop(ctx):
    ctx.voice_client.stop()

# -------------------------------
# PLAYLIST MEMORY COMMANDS
# -------------------------------
@bot.command()
async def saveplaylist(ctx, name):
    player = get_player(ctx.guild)
    playlist_file = get_playlist_file(ctx.author.id, name)

    if not player.queue:
        return await ctx.send("Queue is empty, nothing to save.")

    songs = list(player.queue)
    with open(playlist_file, "w", encoding="utf-8") as f:
        json.dump(songs, f, indent=4)

    await ctx.send(f"Playlist **{name}** saved! 💾")

@bot.command()
async def loadplaylist(ctx, name):
    player = get_player(ctx.guild)
    playlist_file = get_playlist_file(ctx.author.id, name)

    if not playlist_file.exists():
        return await ctx.send("Playlist not found.")

    with open(playlist_file, "r", encoding="utf-8") as f:
        songs = json.load(f)

    for song in songs:
        player.queue.append(song)

    await ctx.send(f"Loaded playlist **{name}** 🎶")

@bot.command()
async def myplaylists(ctx):
    user_dir = get_user_dir(ctx.author.id)
    files = list(user_dir.glob("*.json"))

    if not files:
        return await ctx.send("You have no saved playlists.")

    names = [f.stem for f in files]
    await ctx.send("📀 **Your Playlists:**\n" + "\n".join(f"- {n}" for n in names))

@bot.command()
async def addtoplaylist(ctx, name, *, query):
    """Add a song to a user playlist without touching the queue."""
    
    playlist_file = get_playlist_file(ctx.author.id, name)

    if playlist_file.exists():
        try:
            with open(playlist_file, "r", encoding="utf-8") as f:
                songs = json.load(f)
        except json.JSONDecodeError:
            songs = []  
    else:
        songs = []

    ydl_opts = {"format": "bestaudio", "quiet": True, "noplaylist": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = (ydl.extract_info(query, download=False)
                    if query.startswith("http")
                    else ydl.extract_info(f"ytsearch:{query}", download=False)["entries"][0])
    except Exception as e:
        return await ctx.send(f"❌ Could not find that song.\nError: `{str(e)}`")


    song = {
        "title": info.get("title", "Unknown Title"),
        "url": info["url"],
        "webpage_url": info.get("webpage_url"),
        "id": info.get("id")
    }

    songs.append(song)

    with open(playlist_file, "w", encoding="utf-8") as f:
        json.dump(songs, f, indent=4)

    await ctx.send(f"📀 Added **{song['title']}** to playlist **{name}**! 🎧")

# -------------------------------
# ROLE COMMANDS
# -------------------------------
@bot.command()
async def assign(ctx):
    role = discord.utils.get(ctx.guild.roles, name=secret_role)
    if role:
        await ctx.author.add_roles(role)
        await ctx.send(f"{ctx.author.mention} is now assigned to {secret_role}.")
    else:
        await ctx.send("Role not found.")

@bot.command()
async def remove(ctx):
    role = discord.utils.get(ctx.guild.roles, name=secret_role)
    if role:
        await ctx.author.remove_roles(role)
        await ctx.send(f"{ctx.author.mention} has been removed from {secret_role}.")
    else:
        await ctx.send("Role not found.")


@bot.command()
@commands.has_role(secret_role)
async def secret(ctx):
    await ctx.send("Welcome to the club!")

@secret.error
async def secret_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("You do not have the required role to use this command.")
        
@bot.event
async def on_voice_state_update(member, before, after):
    voice_client = member.guild.voice_client


    if not voice_client:
        return

    if voice_client.channel and len(voice_client.channel.members) == 1:
        await asyncio.sleep(120)


        if len(voice_client.channel.members) == 1:
            await voice_client.disconnect()



# -------------------------------
# RUN
# -------------------------------
if not token:
    print("ERROR: DISCORD_TOKEN not set in environment.")
else:
    bot.run(token, log_handler=handler, log_level=logging.DEBUG)