import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import datetime

load_dotenv()  # loads DISCORD_BOT_TOKEN from .env
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.members = True # Required to get member information
intents.message_content = True

bot = commands.Bot(command_prefix=">", intents=intents) # Changed prefix to >

# In-memory storage for salute cooldowns. For a real bot, you'd want a database.
salute_cooldowns = {}

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

@bot.command()
async def ping(ctx):
    await ctx.reply("Pong!")

@bot.command()
async def salute(ctx, member: discord.Member):
    """Salute another user to give them XP."""
    author_id = ctx.author.id
    current_time = datetime.datetime.now()

    # Check for cooldown
    if author_id in salute_cooldowns:
        last_salute_time = salute_cooldowns[author_id]
        if current_time - last_salute_time < datetime.timedelta(minutes=5):
            await ctx.reply("You can only salute once every 5 minutes.")
            return

    # Grant XP (for now, we'll just send a message)
    # In the future, you could replace this with a real XP system.
    await ctx.send(f"{ctx.author.mention} salutes {member.mention}! They have gained 10 XP.")

    # Update the cooldown
    salute_cooldowns[author_id] = current_time

@salute.error
async def salute_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply("Please mention a user to salute. Usage: `>salute @user`")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.reply("Could not find that member. Please make sure you've mentioned a valid user.")
    else:
        # For other errors, you can log them or send a generic error message.
        print(f"An error occurred with the salute command: {error}")
        await ctx.reply("An unexpected error occurred.")


bot.run(TOKEN)