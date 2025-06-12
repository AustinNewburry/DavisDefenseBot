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

    # Grant XP
    xp_to_give = random.randint(5, 15)
    if member_id not in user_xp:
        user_xp[member_id] = 0
    user_xp[member_id] += xp_to_give
    save_xp(user_xp)

    await ctx.send(f"o7 {ctx.author.mention} salutes {member.mention}! They have gained {xp_to_give} XP.")

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

@bot.command()
async def xp(ctx, member: discord.Member = None):
    """Check your or another user's XP."""
    if member is None:
        member = ctx.author

    member_id = str(member.id)
    xp_amount = user_xp.get(member_id, 0)

    await ctx.reply(f"{member.display_name} has {xp_amount} XP.")

@bot.command()
@commands.is_owner()
async def setxp(ctx, member: discord.Member, amount: int):
    """(Owner only) Set a user's XP to a specific amount."""
    if ctx.author.id != OWNER_ID:
        return

    member_id = str(member.id)
    user_xp[member_id] = amount
    save_xp(user_xp)
    await ctx.reply(f"Set {member.mention}'s XP to {amount}.")

@bot.command()
@commands.is_owner()
async def addxp(ctx, member: discord.Member, amount: int):
    """(Owner only) Add XP to a user."""
    if ctx.author.id != OWNER_ID:
        return

    member_id = str(member.id)
    if member_id not in user_xp:
        user_xp[member_id] = 0
    user_xp[member_id] += amount
    save_xp(user_xp)
    await ctx.reply(f"Added {amount} XP to {member.mention}. They now have {user_xp[member_id]} XP.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.NotOwner):
        await ctx.reply("You do not have permission to use this command.")
    else:
        pass


bot.run(TOKEN)