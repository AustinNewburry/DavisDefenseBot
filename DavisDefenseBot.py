import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import datetime
import json
import random
import asyncio

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

OWNER_ID = 819414821182242848

# --- Bot Configuration ---
ATTACK_CHANNEL_ID = 0
NOTIFICATION_ROLE_NAME = "HDAAF Notifications"
ANNOUNCEMENT_CHANNEL_NAME = "hdaaf-announcements"
EMO_HUNTER_ROLE_NAME = "Emo Hunter"

# --- Role & XP Structure ---
# This is the master list of all possible ranks for calculating weight and checking manual assignments.
RANK_ROLES = [
    {"name": "Private", "xp": 0, "weight": 1},
    {"name": "Private First Class", "xp": 150, "weight": 2},
    {"name": "Corporal", "xp": 600, "weight": 3},
    {"name": "Sergeant", "xp": 1350, "weight": 4},
    {"name": "Staff Sergeant", "xp": 2400, "weight": 5},
    {"name": "Master Sergeant", "xp": 3750, "weight": 6},
    {"name": "Sergeant Major", "xp": 5400, "weight": 7},
    {"name": "Lieutenant", "xp": 7350, "weight": 8},
    {"name": "Captain", "xp": 9600, "weight": 9},
    {"name": "Major", "xp": 12150, "weight": 10},
    {"name": "Colonel", "xp": 15000, "weight": 11},
    {"name": "Brigadier General", "xp": 18150, "weight": 12},
    {"name": "General", "xp": 21600, "weight": 13},
    {"name": "General of the Army", "xp": 25350, "weight": 15}
]
# This is the list of roles the bot can automatically assign via XP.
ACQUIRABLE_RANK_ROLES = RANK_ROLES[:11] # Up to Colonel

RANK_ROLE_NAMES = {role["name"] for role in RANK_ROLES}

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Set the owner ID when creating the bot instance
bot = commands.Bot(command_prefix=">", intents=intents, owner_id=OWNER_ID)
bot.remove_command('help') # Remove default help command

# --- Global State & Cooldowns ---
game_features_enabled = True # Master switch for game features
attack_in_progress = False
defenders = set()
patrol_cooldowns = {}
salute_cooldowns = {}
boss_event_active = False
boss_hp = 0
boss_max_hp = 0
boss_title = ""
boss_participants = set()

# --- Data File Management ---
XP_FILE = "xp.json"
STATS_FILE = "user_stats.json"

def load_data(file_path):
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        with open(file_path, "r") as f:
            return json.load(f)
    return {}

def save_data(data, file_path):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

user_xp = load_data(XP_FILE)
user_stats = load_data(STATS_FILE)

# --- Role Management ---
async def check_and_update_roles(member: discord.Member):
    if not game_features_enabled: return
    user_id = str(member.id)
    current_xp = user_xp.get(user_id, 0)
    target_role_data = None
    # Use the acquirable roles list for automatic promotions
    for rank in reversed(ACQUIRABLE_RANK_ROLES):
        if current_xp >= rank["xp"]:
            target_role_data = rank
            break
    if not target_role_data: return
    target_role_name = target_role_data["name"]
    target_role_obj = discord.utils.get(member.guild.roles, name=target_role_name)
    if target_role_obj and target_role_obj not in member.roles:
        await member.add_roles(target_role_obj, reason="Automatic promotion via XP")

# --- UI Views ---
class PatrolEncounterView(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=30.0)
        self.author = author
        self.result = None
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This is not your patrol!", ephemeral=True)
            return False
        return True
    @discord.ui.button(label="Attack", style=discord.ButtonStyle.red)
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = "attack"; self.stop(); await interaction.response.defer()
    @discord.ui.button(label="Retreat", style=discord.ButtonStyle.secondary)
    async def retreat(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = "retreat"; self.stop(); await interaction.response.defer()
    async def on_timeout(self):
        self.result = "timeout"

# --- Bot Events & Tasks ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    if game_features_enabled:
        attack_scheduler.start()
        print("Game features are ENABLED. Attack scheduler started.")
    else:
        print("Game features are DISABLED.")

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if not game_features_enabled: return
    if before.roles == after.roles: return
    # Use the full list to check for manual assignments of any rank
    member_rank_roles = [role for role in after.roles if role.name in RANK_ROLE_NAMES]
    if not member_rank_roles: return
    highest_rank_owned = None
    # Use the full list to determine the highest role
    for rank_data in RANK_ROLES:
        for member_role in member_rank_roles:
            if rank_data["name"] == member_role.name:
                highest_rank_owned = rank_data
    if not highest_rank_owned: return
    baseline_xp = highest_rank_owned["xp"]
    user_id = str(after.id)
    current_xp = user_xp.get(user_id, 0)
    if current_xp < baseline_xp:
        user_xp[user_id] = baseline_xp
        save_data(user_xp, XP_FILE)
        print(f"Updated {after.display_name}'s XP to {baseline_xp} to match their highest role: '{highest_rank_owned['name']}'.")

@tasks.loop(minutes=1)
async def attack_scheduler():
    global attack_in_progress
    if not game_features_enabled: return
    if not attack_in_progress and random.randint(1, 120) == 1:
        channel = bot.get_channel(ATTACK_CHANNEL_ID)
        if channel: await initiate_attack(channel)
        else: print(f"Error: Attack channel with ID {ATTACK_CHANNEL_ID} not found.")

@attack_scheduler.before_loop
async def before_attack_scheduler(): await bot.wait_until_ready()

# --- Game Logic ---
async def resolve_attack(channel: discord.TextChannel):
    global attack_in_progress, defenders
    if not defenders:
        await channel.send("The attack was undefended! Davis has fallen into chaos.")
        attack_in_progress = False
        return
    defense_strength = 0; defender_details = []; guild = channel.guild
    for user_id in defenders:
        member = guild.get_member(user_id)
        if member:
            member_rank_weight = 1
            for rank_info in reversed(RANK_ROLES): # Use full list for weight
                for role in member.roles:
                    if role.name == rank_info["name"]:
                        member_rank_weight = rank_info["weight"]; break
                if member_rank_weight > 1: break
            defense_strength += member_rank_weight
            defender_details.append(f"{member.display_name} (Rank Power: {member_rank_weight})")
    attack_strength = random.randint(int(defense_strength * 0.7), int(defense_strength * 1.5)) + 5
    embed = discord.Embed(title="Battle Report", color=discord.Color.dark_red())
    embed.add_field(name="Defenders", value="\n".join(defender_details) or "None", inline=False)
    embed.add_field(name="Total Defense Strength", value=str(defense_strength), inline=True)
    embed.add_field(name="Attack Strength", value=str(attack_strength), inline=True)
    if defense_strength >= attack_strength:
        embed.description = "🎉 **VICTORY!** The defenders have successfully repelled the attack!"; embed.color = discord.Color.green()
        xp_reward = random.randint(50, 100)
        embed.set_footer(text=f"Each defender has been awarded {xp_reward} XP for their bravery.")
        for user_id in defenders:
            str_id = str(user_id); user_xp[str_id] = user_xp.get(str_id, 0) + xp_reward
        save_data(user_xp, XP_FILE)
        for user_id in defenders:
            member = guild.get_member(user_id)
            if member: await check_and_update_roles(member)
    else:
        embed.description = "☠️ **DEFEAT!** The attack was too strong and broke through the defenses."; embed.color = discord.Color.red()
    await channel.send(embed=embed)
    attack_in_progress = False; defenders = set()

async def initiate_attack(channel: discord.TextChannel):
    global attack_in_progress, defenders
    attack_in_progress = True; defenders = set()
    notification_role = discord.utils.get(channel.guild.roles, name=NOTIFICATION_ROLE_NAME)
    ping_message = f"{notification_role.mention}" if notification_role else ""
    embed = discord.Embed(title="🚨 INCOMING ATTACK! 🚨", description="An enemy force is approaching Davis! All personnel must defend!", color=discord.Color.orange())
    embed.add_field(name="Time to React", value="60 seconds"); embed.add_field(name="How to Fight", value="Type `>defend` in this channel to join the battle!")
    embed.set_footer(text="Your rank determines your power in the fight.")
    await channel.send(ping_message, embed=embed)
    await asyncio.sleep(60)
    await resolve_attack(channel)

async def resolve_world_boss(channel: discord.TextChannel):
    global boss_event_active, boss_hp, boss_participants, boss_title
    embed = discord.Embed(color=discord.Color.gold())
    if boss_hp <= 0:
        embed.title = f"🎉 WORLD BOSS DEFEATED! 🎉"; embed.description = f"**{boss_title}** has been vanquished by the brave soldiers of Davis!"
        xp_reward = random.randint(250, 500)
        embed.set_footer(text=f"All {len(boss_participants)} participants have been awarded {xp_reward} XP!")
        for user_id in boss_participants:
            str_id = str(user_id); user_xp[str_id] = user_xp.get(str_id, 0) + xp_reward
            member = channel.guild.get_member(user_id)
            if member: await check_and_update_roles(member)
        save_data(user_xp, XP_FILE)
    else:
        embed.title = f"☠️ WORLD BOSS SURVIVED ☠️"; embed.description = f"**{boss_title}** was too powerful and escaped before it could be defeated."
        embed.set_footer(text="No XP was awarded. Better luck next time!")
    await channel.send(embed=embed)
    boss_event_active = False; boss_participants = set()

# --- Commands ---
# ... (Toggle commands, Utility commands remain the same) ...

# --- Game Commands ---
@bot.command()
async def patrol(ctx):
    if not game_features_enabled: return
    # ... (Patrol logic remains the same, using full RANK_ROLES for weight calc) ...

# ... (All other commands remain the same) ...

@bot.command()
@commands.is_owner()
async def gameon(ctx):
    global game_features_enabled
    if game_features_enabled: return await ctx.reply("Game features are already enabled.")
    game_features_enabled = True
    if not attack_scheduler.is_running(): attack_scheduler.start()
    await ctx.reply("✅ Game features have been **ENABLED**. The attack scheduler is now running.")

@bot.command()
@commands.is_owner()
async def gameoff(ctx):
    global game_features_enabled
    if not game_features_enabled: return await ctx.reply("Game features are already disabled.")
    game_features_enabled = False
    if attack_scheduler.is_running(): attack_scheduler.cancel()
    await ctx.reply("❌ Game features have been **DISABLED**. The attack scheduler is now stopped.")

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(title="Davis Defense Bot Commands", description="Here are the commands you can use:", color=discord.Color.gold())
    embed.add_field(name="`>xp [@user]`", value="Check your own XP or another user's.", inline=False)
    embed.add_field(name="`>salute [@user]`", value="Give another user a small amount of XP (5 min cooldown).", inline=False)
    if game_features_enabled:
        game_commands_value = ("**`>patrol`**: Go on patrol for a chance at XP or an encounter (5 min cooldown).\n""**`>defend`**: Join the defense during a server-wide attack.\n""**`>hit`**: Attack the world boss during a boss event.")
        embed.add_field(name="Game Commands (Active)", value=game_commands_value, inline=False)
    else:
        embed.add_field(name="Game Commands (Disabled)", value="The main game features are currently disabled by the owner.", inline=False)
    embed.add_field(name="`>ping`", value="Check if the bot is responsive (5 min global cooldown).", inline=False)
    embed.set_footer(text="Owner-only commands are hidden.")
    await ctx.send(embed=embed)

@bot.command()
@commands.is_owner()
async def announce(ctx, *, message: str):
    channel = discord.utils.get(ctx.guild.channels, name=ANNOUNCEMENT_CHANNEL_NAME)
    if not channel: return await ctx.reply(f"I couldn't find the `#{ANNOUNCEMENT_CHANNEL_NAME}` channel.")
    embed = discord.Embed(title="📢 Announcement", description=message, color=discord.Color.blue(), timestamp=datetime.datetime.now())
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    try:
        await channel.send(embed=embed); await ctx.message.add_reaction('✅')
    except discord.Forbidden:
        await ctx.reply(f"I don't have permission to send messages in {channel.mention}.")

@bot.command()
@commands.is_owner()
async def say(ctx, channel: discord.TextChannel, *, message: str):
    try:
        await channel.send(message); await ctx.message.add_reaction('✅')
    except discord.Forbidden:
        await ctx.reply(f"I don't have permission to send messages in {channel.mention}.")

@bot.command()
@commands.cooldown(1, 300, commands.BucketType.default)
async def ping(ctx):
    ping_message = ("> PING: HENRY DAVIS DEFENSE ROBOT [ID: HD-DRX-0923]\n""...""[H.D.D.R]: “I SEE EVERYTHING.”\n""```\n""> END PING RESPONSE\n""> LOG CODE: 7B3F-A119-CX99")
    await ctx.reply(ping_message)

@bot.command()
async def patrol(ctx):
    if not game_features_enabled: return
    author_id = str(ctx.author.id)
    current_time = datetime.datetime.now()
    if author_id in patrol_cooldowns:
        if current_time - patrol_cooldowns[author_id] < datetime.timedelta(minutes=5):
            return await ctx.reply("You need to rest. You can go on patrol again in 5 minutes.")
    patrol_cooldowns[author_id] = current_time
    if random.random() > 0.5:
        xp_reward = random.randint(5, 10); user_xp[author_id] = user_xp.get(author_id, 0) + xp_reward
        save_data(user_xp, XP_FILE); await check_and_update_roles(ctx.author)
        return await ctx.reply(f"Your patrol was uneventful. You secured the area and gained {xp_reward} XP.")
    embed = discord.Embed(title="Patrol Encounter!", description="You've encountered a band of violent emos! They look hostile.", color=discord.Color.dark_purple())
    embed.set_footer(text="What will you do?")
    view = PatrolEncounterView(ctx.author)
    message = await ctx.reply(embed=embed, view=view)
    await view.wait()
    for item in view.children: item.disabled = True
    await message.edit(view=view)
    if view.result in ("retreat", "timeout"):
        result_embed = discord.Embed(title="Patrol Ended", description="You chose to retreat, avoiding a risky fight.", color=discord.Color.light_grey())
        return await message.edit(embed=result_embed)
    if view.result == "attack":
        member_rank_weight = 1
        for rank_info in reversed(RANK_ROLES): # Use full list for weight
            for role in ctx.author.roles:
                if role.name == rank_info["name"]: member_rank_weight = rank_info["weight"]; break
            if member_rank_weight > 1: break
        win_chance = min(0.30 + (member_rank_weight * 0.05), 0.95)
        if random.random() < win_chance:
            xp_reward = random.randint(75, 150); user_xp[author_id] = user_xp.get(author_id, 0) + xp_reward
            save_data(user_xp, XP_FILE)
            stats = user_stats.get(author_id, {"patrol_wins": 0}); stats["patrol_wins"] += 1
            user_stats[author_id] = stats; save_data(user_stats, STATS_FILE)
            if stats["patrol_wins"] >= 100:
                hunter_role = discord.utils.get(ctx.guild.roles, name=EMO_HUNTER_ROLE_NAME)
                if hunter_role and hunter_role not in ctx.author.roles:
                    await ctx.author.add_roles(hunter_role, reason="Achieved Emo Hunter status")
                    await ctx.send(f"Congratulations, {ctx.author.mention}! For winning 100 patrol encounters, you have been awarded the **{EMO_HUNTER_ROLE_NAME}** role!")
            result_embed = discord.Embed(title="VICTORY!", description=f"You bravely fought and defeated the emos! You earned {xp_reward} XP for your valor.", color=discord.Color.green())
            await message.edit(embed=result_embed)
        else:
            result_embed = discord.Embed(title="DEFEAT!", description="The emos were stronger than they looked. You were defeated but managed to escape. You earned no XP.", color=discord.Color.red())
            await message.edit(embed=result_embed)

@bot.command()
@commands.is_owner()
async def worldboss(ctx, *, params: str):
    if not game_features_enabled: return
    global boss_event_active, boss_hp, boss_max_hp, boss_title, boss_participants
    if boss_event_active: return await ctx.reply("A world boss event is already in progress.")
    try:
        title, description, health_str = [p.strip() for p in params.split('|')]
        health = int(health_str)
    except ValueError:
        return await ctx.reply("Invalid format. Use: `>worldboss Title | Description | Health`")
    boss_event_active = True; boss_hp = health; boss_max_hp = health
    boss_title = title; boss_participants = set()
    notification_role = discord.utils.get(ctx.guild.roles, name=NOTIFICATION_ROLE_NAME)
    if not notification_role:
        await ctx.reply(f"⚠️ **Warning:** Could not find the role `{NOTIFICATION_ROLE_NAME}`. The event will start without a ping.", delete_after=15)
        ping_message = ""
    else:
        ping_message = notification_role.mention
    embed = discord.Embed(title=f"🚨 WORLD BOSS EVENT! 🚨", description=description, color=discord.Color.magenta())
    embed.set_author(name=title)
    embed.add_field(name="Health", value=f"{boss_hp}/{boss_max_hp} HP")
    embed.add_field(name="Time Limit", value="60 seconds")
    embed.add_field(name="How to Fight", value="Type `>hit` to attack!")
    await ctx.send(ping_message, embed=embed)
    await asyncio.sleep(60)
    await resolve_world_boss(ctx.channel)

@bot.command()
async def hit(ctx):
    if not game_features_enabled: return
    global boss_event_active, boss_hp, boss_participants
    if not boss_event_active: return
    if ctx.author.id in boss_participants: return await ctx.reply("You have already attacked this boss!", delete_after=10)
    boss_participants.add(ctx.author.id)
    member_rank_weight = 1
    for rank_info in reversed(RANK_ROLES): # Use full list for weight
        for role in ctx.author.roles:
            if role.name == rank_info["name"]: member_rank_weight = rank_info["weight"]; break
        if member_rank_weight > 1: break
    damage = random.randint(50, 100) * member_rank_weight
    boss_hp -= damage
    await ctx.send(f"**{ctx.author.display_name}** hits **{boss_title}** for **{damage}** damage! (HP: {max(0, boss_hp)}/{boss_max_hp})")

@bot.command()
async def defend(ctx):
    if not game_features_enabled: return
    global attack_in_progress, defenders
    if not attack_in_progress: return await ctx.reply("There is no attack to defend against right now.", delete_after=10)
    if ctx.author.id in defenders: return await ctx.reply("You are already in the defensive line!", delete_after=10)
    defenders.add(ctx.author.id); await ctx.message.add_reaction("🛡️")

@bot.command()
@commands.is_owner()
async def forceattack(ctx):
    if not game_features_enabled: return
    if attack_in_progress: return await ctx.reply("An attack is already in progress.")
    await ctx.reply("Forcing an attack now..."); bot.loop.create_task(initiate_attack(ctx.channel))

@bot.command()
async def salute(ctx, member: discord.Member):
    if not game_features_enabled: return
    author_id = str(ctx.author.id)
    current_time = datetime.datetime.now()
    if ctx.author == member: return await ctx.reply("You cannot salute yourself.")
    if author_id in salute_cooldowns:
        if current_time - salute_cooldowns[author_id] < datetime.timedelta(minutes=5):
            return await ctx.reply("You can only salute once every 5 minutes.")
    salute_cooldowns[author_id] = current_time
    xp_to_give = random.randint(5, 15)
    member_id = str(member.id)
    user_xp[member_id] = user_xp.get(member_id, 0) + xp_to_give
    save_data(user_xp, XP_FILE)
    await check_and_update_roles(member)
    await ctx.send(f"o7 {ctx.author.mention} salutes {member.mention}! They have gained {xp_to_give} XP.")

@bot.command()
async def xp(ctx, member: discord.Member = None):
    if not game_features_enabled: return
    if member is None: member = ctx.author
    member_id = str(member.id); xp_amount = user_xp.get(member_id, 0)
    await ctx.reply(f"{member.display_name} has {xp_amount} XP.")

@bot.command()
@commands.is_owner()
async def setxp(ctx, member: discord.Member, amount: int):
    if not game_features_enabled: return
    member_id = str(member.id); user_xp[member_id] = amount; save_data(user_xp, XP_FILE)
    await check_and_update_roles(member)
    await ctx.reply(f"Set {member.mention}'s XP to {amount}.")

@bot.command()
@commands.is_owner()
async def addxp(ctx, member: discord.Member, amount: int):
    if not game_features_enabled: return
    member_id = str(member.id); user_xp[member_id] = user_xp.get(member_id, 0) + amount; save_data(user_xp, XP_FILE)
    await check_and_update_roles(member)
    await ctx.reply(f"Added {amount} XP to {member.mention}. They now have {user_xp[member_id]} XP.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(f"This command is on cooldown. Please try again in {error.retry_after:.2f}s.")
    elif isinstance(error, commands.NotOwner):
        await ctx.reply("You do not have permission to use this command.")
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.reply(f"I could not find the channel you specified.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"You're missing a required argument for this command.")
    else:
        print(f"An unhandled error occurred: {error}")

bot.run(TOKEN)
