import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import yt_dlp

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default() 
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

secret_role = "gamer"
@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user.name}')

@bot.event
async def on_member_join(member):
    await member.send(f'Welcome to the server, {member.name}!')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if "shit" in message.content.lower():
        await message.delete()
        await message.channel.send(f'{message.author.mention}, please refrain from using inappropriate language.')
        
    await bot.process_commands(message)
    
@bot.command()
async def hello(ctx):
    await ctx.send(f'Hello {ctx.author.name}!')
    
@bot.command()
async def assign(ctx):
    role = discord.utils.get(ctx.guild.roles, name=secret_role)
    if role:
        await ctx.author.add_roles(role)
        await ctx.send(f'{ctx.author.mention} is now assigned to {secret_role}.')
    else:
        await ctx.send('Role not found.') 
        
@bot.command()
async def remove(ctx):
    role = discord.utils.get(ctx.guild.roles, name=secret_role)
    if role:
        await ctx.author.remove_roles(role)
        await ctx.send(f'{ctx.author.mention} has been removed from {secret_role}.')
    else:
        await ctx.send('Role not found.')
        
@bot.command()
async def dm(ctx, * ,msg):
    await ctx.author.send('This is a direct message!')
    
@bot.command()
async def reply(ctx):
    await ctx.reply('hello there')
    
@bot.command()
async def poll(ctx, * ,question):
    embed=discord.Embed(title="Poll", description=question, color=discord.Color.blue())
    poll_message = await ctx.send(embed=embed)
    await poll_message.add_reaction("👍")
    await poll_message.add_reaction("👎")
    
@bot.command()
async def join(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()
    else:
        await ctx.send("You must be in a voice channel to use this.")
        
@bot.command()
@commands.is_owner()  
async def shutdown(ctx):
    await ctx.send("Shutting down... 👋")
    await bot.close()

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        

@bot.command()
async def play(ctx, *, query):
    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("Join a voice channel first!")
            return

    ydl_opts = {
        "format": "bestaudio",
        "quiet": True,
        "noplaylist": True  
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        if query.startswith("http"):
            info = ydl.extract_info(query, download=False)
        else:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)["entries"][0]

        audio_url = info["url"]

    ffmpeg_options = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn"
    }


    source = await discord.FFmpegOpusAudio.from_probe(audio_url, **ffmpeg_options)
    ctx.voice_client.play(source)


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

    

@bot.command()
@commands.has_role(secret_role)
async def secret(ctx):
    await ctx.send('Welcome to the club!')
    
@secret.error
async def secret_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send('you do not have the required role to use this command.')

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
