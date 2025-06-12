import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import datetime
import json
import random

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

OWNER_ID = 819414821182242848

# --- Role & XP Structure ---
# The bot will grant roles based on this list.
# The XP is the *minimum* required for that role.
# It's ordered from lowest to highest rank.
RANK_ROLES = [
    {"name": "Private", "xp": 0},
    {"name": "Private First Class", "xp": 150},
    {"name": "Corporal", "xp": 600},
    {"name": "Sergeant", "xp": 1350},
    {"name": "Staff Sergeant", "xp": 2400},
    {"name": "Master Sergeant", "xp": 3750},
    {"name": "Sergeant Major", "xp": 5400},
    {"name": "Lieutenant", "xp": 7350},
    {"name": "Captain", "xp": 9600},
    {"name": "Major", "xp": 12150},
    {"name": "Colonel", "xp": 15000},
    {"name": "Brigadier General", "xp": 18150},
    {"name": "General", "xp": 21600},
    {"name": "General of the Army", "xp": 25350}
]
# Create a set of just the role names for easier checking
RANK_ROLE_NAMES = {role["name"] for role in RANK_ROLES}


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=">", intents=intents)

# In-memory storage for salute cooldowns
salute_cooldowns = {}

# XP System
XP_FILE = "xp.json"

def load_xp():
    # Check if the file exists and is not empty
    if os.path.exists(XP_FILE) and os.path.getsize(XP_FILE) > 0:
        with open(XP_FILE, "r") as f:
            return json.load(f)
    return {} # Return an empty dictionary if the file is empty or doesn't exist

def save_xp(user_xp):
    with open(XP_FILE, "w") as f:
        json.dump(user_xp, f, indent=4)

user_xp = load_xp()

async def check_and_update_roles(member: discord.Member):
    """Checks a user's XP and updates their rank role accordingly."""
    user_id = str(member.id)
    current_xp = user_xp.get(user_id, 0)

    # Determine the highest role the user has earned
    target_role_name = None
    for rank in reversed(RANK_ROLES): # Iterate from highest to lowest
        if current_xp >= rank["xp"]:
            target_role_name = rank["name"]
            break

    if not target_role_name:
        return # No roles to assign if they don't meet the minimum for the lowest rank

    # Get the role object from the server
    target_role = discord.utils.get(member.guild.roles, name=target_role_name)
    if not target_role:
        print(f"Warning: Role '{target_role_name}' not found on the server.")
        return

    # Remove any other rank roles the user might have
    roles_to_remove = []
    for user_role in member.roles:
        if user_role.name in RANK_ROLE_NAMES and user_role.name != target_role_name:
            roles_to_remove.append(user_role)

    if roles_to_remove:
        await member.remove_roles(*roles_to_remove, reason="Rank update")

    # Add the new role if they don't already have it
    if target_role not in member.roles:
        await member.add_roles(target_role, reason="Rank promotion")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

@bot.command()
async def ping(ctx):
    await ctx.reply("Pong!")

@bot.command()
async def salute(ctx, member: discord.Member):
    """Salute another user to give them XP."""
    author_id = str(ctx.author.id)
    member_id = str(member.id)
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

    # Check for a role update after granting XP
    await check_and_update_roles(member)

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

    await check_and_update_roles(member)  # Check for role update

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

    await check_and_update_roles(member)  # Check for role update

    await ctx.reply(f"Added {amount} XP to {member.mention}. They now have {user_xp[member_id]} XP.")

@bot.command()
async def xp(ctx, member: discord.Member = None):
    """Check your or another user's XP."""
    if member is None:
        member = ctx.author

    member_id = str(member.id)
    xp_amount = user_xp.get(member_id, 0)

    await ctx.reply(f"{member.display_name} has {xp_amount} XP.")

@salute.error
async def salute_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply("Please mention a user to salute. Usage: `>salute @user`")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.reply("Could not find that member. Please make sure you've mentioned a valid user.")
    else:
        print(f"An error occurred with the salute command: {error}")
        await ctx.reply("An unexpected error occurred.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.NotOwner):
        await ctx.reply("You do not have permission to use this command.")
    else:
        pass


bot.run(TOKEN)