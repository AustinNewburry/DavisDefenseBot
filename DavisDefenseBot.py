import os, discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()  # loads DISCORD_BOT_TOKEN from .env
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

@bot.command()
async def ping(ctx):
    await ctx.reply("Pong!")

bot.run(TOKEN)git --version
$ ^V^V^Vvvvv^V^V

