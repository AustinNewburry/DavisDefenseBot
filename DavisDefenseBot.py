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

# --- Game Data Structures ---
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
ACQUIRABLE_RANK_ROLES = RANK_ROLES[:11]
RANK_ROLE_NAMES = {role["name"] for role in RANK_ROLES}
ACQUIRABLE_RANK_ROLE_NAMES = {role["name"] for role in ACQUIRABLE_RANK_ROLES}
UNACQUIRABLE_RANK_ROLE_NAMES = RANK_ROLE_NAMES - ACQUIRABLE_RANK_ROLE_NAMES

MATERIALS = [
    {"name": "Scrap Metal", "rarity": "common", "emoji": "🔩"},
    {"name": "Gunpowder", "rarity": "common", "emoji": "🧨"},
    {"name": "Duct Tape", "rarity": "common", "emoji": "🩹"},
    {"name": "Electronics", "rarity": "uncommon", "emoji": "⚙️"},
    {"name": "High-Grade Steel", "rarity": "uncommon", "emoji": "🛡️"},
    {"name": "Medical Supplies", "rarity": "uncommon", "emoji": "⚕️"},
    {"name": "Advanced Optics", "rarity": "rare", "emoji": "🔭"},
    {"name": "Military-Grade Composite", "rarity": "rare", "emoji": "🪖"},
    {"name": "Nuclear Material", "rarity": "legendary", "emoji": "☢️"}
]
MATERIAL_RARITY_WEIGHTS = {
    "common": 60,
    "uncommon": 30,
    "rare": 9,
    "legendary": 1
}

RECIPES = {
    "Pipe Bomb": {
        "description": "A simple, yet effective, explosive device.",
        "materials": {"Scrap Metal": 5, "Gunpowder": 3, "Duct Tape": 1}, "emoji": "💣", "type": "consumable"
    },
    "Medkit": {
        "description": "Restores health in the field.",
        "materials": {"Medical Supplies": 5, "Duct Tape": 2}, "emoji": "➕", "type": "consumable"
    },
    "Pistol": {
        "description": "Standard issue sidearm. Adds +2 power.",
        "materials": {"Scrap Metal": 10, "High-Grade Steel": 2}, "emoji": "🔫", "type": "weapon", "weight_bonus": 2
    },
    "Shotgun": {
        "description": "Devastating at close range. Adds +4 power.",
        "materials": {"Scrap Metal": 15, "High-Grade Steel": 5, "Gunpowder": 5}, "emoji": "💥", "type": "weapon",
        "weight_bonus": 4
    },
    "Assault Rifle": {
        "description": "A versatile automatic weapon. Adds +6 power.",
        "materials": {"High-Grade Steel": 10, "Electronics": 5, "Scrap Metal": 20}, "emoji": "🔫", "type": "weapon",
        "weight_bonus": 6
    },
    "Sniper Rifle": {
        "description": "For taking out targets from a distance. Adds +8 power.",
        "materials": {"High-Grade Steel": 15, "Advanced Optics": 2, "Electronics": 3}, "emoji": "🔭", "type": "weapon",
        "weight_bonus": 8
    },
    "Rocket Launcher": {
        "description": "Delivers a high-explosive payload. Adds +12 power.",
        "materials": {"High-Grade Steel": 25, "Electronics": 10, "Gunpowder": 20, "Military-Grade Composite": 5},
        "emoji": "🚀", "type": "weapon", "weight_bonus": 12
    },
    "Body Armor": {
        "description": "Reduces incoming damage. (Passive)",
        "materials": {"High-Grade Steel": 20, "Military-Grade Composite": 10}, "emoji": "🦺", "type": "armor"
    },
    "Nightvision Goggles": {
        "description": "Grants the ability to see in the dark. (Passive)",
        "materials": {"Electronics": 15, "Advanced Optics": 5, "Duct Tape": 5}, "emoji": "🥽", "type": "gear"
    },
    "Suppressor": {
        "description": "Reduces weapon noise. (Passive)",
        "materials": {"Scrap Metal": 15, "Electronics": 1}, "emoji": "🤫", "type": "gear"
    },
    "Tactical Nuke": {
        "description": "The ultimate weapon. Use with extreme caution.",
        "materials": {"Nuclear Material": 3, "Military-Grade Composite": 20, "Electronics": 30, "High-Grade Steel": 50},
        "emoji": "☢️", "type": "consumable"
    },
    "Coast Guard Battleship": {
        "description": "A formidable naval vessel.",
        "materials": {"Nuclear Material": 10, "High-Grade Steel": 200, "Military-Grade Composite": 100,
                      "Electronics": 150, "Advanced Optics": 50}, "emoji": "🚢", "type": "vehicle"
    }
}

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=">", intents=intents, owner_id=OWNER_ID)
bot.remove_command('help')

# --- Global State & Cooldowns ---
game_features_enabled = True
attack_in_progress = False
defenders = []
patrol_cooldowns = {}
salute_cooldowns = {}
scavenge_cooldowns = {}
boss_event_active = False
boss_hp = 0
boss_max_hp = 0
boss_title = ""
boss_participants = set()
boss_event_message = None

# --- Data File Management ---
XP_FILE = "xp.json"
STATS_FILE = "user_stats.json"
ARMORY_FILE = "armory.json"


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
user_armory = load_data(ARMORY_FILE)


# --- Helper Functions ---
def create_health_bar(current_hp, max_hp, length=20):
    current_hp = max(0, current_hp)
    percentage = current_hp / max_hp
    filled_length = int(length * percentage)
    bar = '█' * filled_length + '─' * (length - filled_length)
    return f"`[{bar}]`\n**{current_hp} / {max_hp} HP**"


# --- Role Management ---
async def check_and_update_roles(member: discord.Member):
    if not game_features_enabled: return
    for role in member.roles:
        if role.name in UNACQUIRABLE_RANK_ROLE_NAMES:
            return
    user_id = str(member.id)
    current_xp = user_xp.get(user_id, 0)
    target_role_data = None
    for rank in reversed(ACQUIRABLE_RANK_ROLES):
        if current_xp >= rank["xp"]:
            target_role_data = rank
            break
    if not target_role_data: return
    target_role_name = target_role_data["name"]
    target_role_obj = discord.utils.get(member.guild.roles, name=target_role_name)
    if not target_role_obj:
        print(f"Warning: Role '{target_role_name}' not found on server.")
        return
    roles_to_remove = []
    for role in member.roles:
        if role.name in ACQUIRABLE_RANK_ROLE_NAMES and role.name != target_role_name:
            roles_to_remove.append(role)
    if roles_to_remove:
        await member.remove_roles(*roles_to_remove, reason="Rank promotion cleanup")
    if target_role_obj not in member.roles:
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
        self.result = "attack";
        self.stop();
        await interaction.response.defer()

    @discord.ui.button(label="Retreat", style=discord.ButtonStyle.secondary)
    async def retreat(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = "retreat";
        self.stop();
        await interaction.response.defer()

    async def on_timeout(self):
        self.result = "timeout"


class ArmoryView(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=120.0)
        self.author = author
        self.current_page = "inventory"
        self.add_item(CraftingSelect(author))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This is not your armory!", ephemeral=True)
            return False
        return True

    async def generate_embed(self):
        member_id = str(self.author.id)
        armory_data = user_armory.get(member_id, {"materials": {}, "crafted_items": {}})
        embed = discord.Embed(color=discord.Color.dark_gray())
        embed.set_author(name=f"{self.author.display_name}'s Armory", icon_url=self.author.display_avatar.url)

        if self.current_page == "inventory":
            embed.title = "Inventory"
            materials = armory_data.get("materials", {})
            crafted_items = armory_data.get("crafted_items", {})
            if not materials:
                embed.add_field(name="Crafting Materials", value="None", inline=False)
            else:
                material_emojis = {m["name"]: m["emoji"] for m in MATERIALS}
                mat_description = "\n".join(
                    [f"{material_emojis.get(name, '❔')} **{name}**: {amount}" for name, amount in
                     sorted(materials.items())])
                embed.add_field(name="Crafting Materials", value=mat_description, inline=False)
            if not crafted_items:
                embed.add_field(name="Crafted Items", value="None", inline=False)
            else:
                item_emojis = {i: r["emoji"] for i, r in RECIPES.items()}
                item_description = "\n".join([f"{item_emojis.get(name, '🛠️')} **{name}**: {amount}" for name, amount in
                                              sorted(crafted_items.items())])
                embed.add_field(name="Crafted Items", value=item_description, inline=False)

        elif self.current_page == "crafting":
            embed.title = "Crafting Menu"
            embed.description = "Select an item from the dropdown below to craft it."
            for name, recipe in RECIPES.items():
                mats_needed = ", ".join([f"{amt}x {mat}" for mat, amt in recipe["materials"].items()])
                embed.add_field(name=f"{recipe['emoji']} {name}", value=f"**Requires:** {mats_needed}", inline=False)

        return embed

    @discord.ui.button(label="View Inventory", style=discord.ButtonStyle.secondary, emoji="�")
    async def inventory_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = "inventory"
        embed = await self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="View Crafting", style=discord.ButtonStyle.secondary, emoji="🛠️")
    async def crafting_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = "crafting"
        embed = await self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)


class CraftingSelect(discord.ui.Select):
    def __init__(self, author: discord.Member):
        self.author = author
        options = [discord.SelectOption(label=name, emoji=recipe["emoji"], description=recipe["description"][:100]) for
                   name, recipe in RECIPES.items()]
        super().__init__(placeholder="Choose an item to craft...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        item_to_craft = self.values[0]
        recipe = RECIPES[item_to_craft]
        author_id = str(self.author.id)

        if author_id not in user_armory:
            user_armory[author_id] = {"materials": {}, "crafted_items": {}}

        user_mats = user_armory[author_id].get("materials", {})

        can_craft = True
        missing_mats = []
        for mat, required in recipe["materials"].items():
            if user_mats.get(mat, 0) < required:
                can_craft = False
                missing_mats.append(f"**{required - user_mats.get(mat, 0)}** more `{mat}`")

        if not can_craft:
            await interaction.response.send_message(
                f"You can't craft **{item_to_craft}**. You still need: {', '.join(missing_mats)}.", ephemeral=True)
            return

        for mat, required in recipe["materials"].items():
            user_armory[author_id]["materials"][mat] -= required

        if "crafted_items" not in user_armory[author_id]:
            user_armory[author_id]["crafted_items"] = {}
        user_armory[author_id]["crafted_items"][item_to_craft] = user_armory[author_id]["crafted_items"].get(
            item_to_craft, 0) + 1

        save_data(user_armory, ARMORY_FILE)

        view = self.view
        if isinstance(view, ArmoryView):
            embed = await view.generate_embed()
            await interaction.response.edit_message(embed=embed, view=view)
            await interaction.followup.send(f"You successfully crafted a {recipe['emoji']} **{item_to_craft}**!",
                                            ephemeral=True)


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
    member_rank_roles = [role for role in after.roles if role.name in RANK_ROLE_NAMES]
    if not member_rank_roles: return
    highest_rank_owned = None
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
        print(
            f"Updated {after.display_name}'s XP to {baseline_xp} to match their highest role: '{highest_rank_owned['name']}'.")
    await check_and_update_roles(after)


@tasks.loop(minutes=1)
async def attack_scheduler():
    global attack_in_progress
    if not game_features_enabled: return
    if not attack_in_progress and random.randint(1, 120) == 1:
        channel = bot.get_channel(ATTACK_CHANNEL_ID)
        if channel:
            await initiate_attack(channel)
        else:
            print(f"Error: Attack channel with ID {ATTACK_CHANNEL_ID} not found.")


@attack_scheduler.before_loop
async def before_attack_scheduler(): await bot.wait_until_ready()


# --- Game Logic ---
async def resolve_attack(channel: discord.TextChannel):
    global attack_in_progress, defenders
    if not defenders:
        await channel.send("The attack was undefended! Davis has fallen into chaos.")
        attack_in_progress = False
        return
    defense_strength = 0;
    defender_details = [];
    guild = channel.guild
    unique_defenders = set(defenders)
    for user_id in defenders:
        member = guild.get_member(user_id)
        if member:
            member_rank_weight = 1
            for rank_info in reversed(RANK_ROLES):
                for role in member.roles:
                    if role.name == rank_info["name"]: member_rank_weight = rank_info["weight"]; break
                if member_rank_weight > 1: break
            defense_strength += (member_rank_weight * 2)
    for user_id in unique_defenders:
        member = guild.get_member(user_id)
        if member: defender_details.append(f"{member.display_name}")
    attack_strength = random.randint(int(defense_strength * 0.7), int(defense_strength * 1.5)) + 5
    embed = discord.Embed(title="Battle Report", color=discord.Color.dark_red())
    embed.add_field(name=f"Defenders ({len(unique_defenders)})", value="\n".join(defender_details) or "None",
                    inline=False)
    embed.add_field(name="Total Defense Strength", value=str(defense_strength), inline=True)
    embed.add_field(name="Attack Strength", value=str(attack_strength), inline=True)
    if defense_strength >= attack_strength:
        embed.description = "🎉 **VICTORY!** The defenders have successfully repelled the attack!";
        embed.color = discord.Color.green()
        xp_reward = random.randint(50, 100)
        embed.set_footer(text=f"Each defender has been awarded {xp_reward} XP for their bravery.")
        for user_id in unique_defenders:
            str_id = str(user_id);
            user_xp[str_id] = user_xp.get(str_id, 0) + xp_reward
        save_data(user_xp, XP_FILE)
        for user_id in unique_defenders:
            member = guild.get_member(user_id)
            if member: await check_and_update_roles(member)
    else:
        embed.description = "☠️ **DEFEAT!** The attack was too strong and broke through the defenses.";
        embed.color = discord.Color.red()
    await channel.send(embed=embed)
    attack_in_progress = False;
    defenders = []


async def initiate_attack(channel: discord.TextChannel):
    global attack_in_progress, defenders
    attack_in_progress = True;
    defenders = []
    notification_role = discord.utils.get(channel.guild.roles, name=NOTIFICATION_ROLE_NAME)
    ping_message = f"{notification_role.mention}" if notification_role else ""
    embed = discord.Embed(title="🚨 INCOMING ATTACK! 🚨",
                          description="An enemy force is approaching Davis! All personnel must defend!",
                          color=discord.Color.orange())
    embed.add_field(name="Time to React", value="60 seconds");
    embed.add_field(name="How to Fight", value="Type `>defend` in this channel to join the battle!")
    embed.set_footer(text="Your rank determines your power in the fight.")
    await channel.send(ping_message, embed=embed)
    await asyncio.sleep(60)
    await resolve_attack(channel)


async def resolve_world_boss(channel: discord.TextChannel):
    global boss_event_active, boss_hp, boss_participants, boss_title, boss_event_message
    final_embed = discord.Embed(color=discord.Color.gold())
    final_embed.set_author(name=boss_title)
    if boss_hp <= 0:
        final_embed.title = f"🎉 WORLD BOSS DEFEATED! 🎉";
        final_embed.description = f"**{boss_title}** has been vanquished by the brave soldiers of Davis!"
        xp_reward = random.randint(250, 500)
        final_embed.set_footer(text=f"All {len(boss_participants)} participants have been awarded {xp_reward} XP!")
        for user_id in boss_participants:
            str_id = str(user_id);
            user_xp[str_id] = user_xp.get(str_id, 0) + xp_reward
            member = channel.guild.get_member(user_id)
            if member: await check_and_update_roles(member)
        save_data(user_xp, XP_FILE)
    else:
        final_embed.title = f"☠️ WORLD BOSS SURVIVED ☠️";
        final_embed.description = f"**{boss_title}** was too powerful and escaped. It remains with {boss_hp} HP."
        final_embed.set_footer(text="No XP was awarded. Better luck next time!")
    if boss_event_message:
        try:
            await boss_event_message.edit(embed=final_embed, view=None)
        except discord.NotFound:
            await channel.send(embed=final_embed)
    boss_event_active = False;
    boss_participants = set();
    boss_event_message = None


# --- Commands ---
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
    embed = discord.Embed(title="Davis Defense Bot Commands", description="Here are the commands you can use:",
                          color=discord.Color.gold())
    embed.add_field(name="`>xp [@user]`", value="Check your own XP or another user's.", inline=False)
    embed.add_field(name="`>salute [@user]`", value="Give another user a small amount of XP (5 min cooldown).",
                    inline=False)
    if game_features_enabled:
        game_commands_value = (
            "**`>patrol`**: Go on patrol for a chance at XP or an encounter (5 min cooldown).\n"
            "**`>scavenge`**: Search for crafting materials (5 min cooldown).\n"
            "**`>armory [@user]`**: Check your interactive inventory and crafting menu.\n"
            "**`>use \"[item name]\"`**: Use a crafted item during a world boss fight.\n"
            "**`>defend`**: Join the defense during a server-wide attack.\n"
            "**`>hit`**: Attack the world boss during a boss event (2s cooldown)."
        )
        embed.add_field(name="Game Commands (Active)", value=game_commands_value, inline=False)
    else:
        embed.add_field(name="Game Commands (Disabled)",
                        value="The main game features are currently disabled by the owner.", inline=False)
    embed.add_field(name="`>ping`", value="Check if the bot is responsive (5 min global cooldown).", inline=False)
    embed.set_footer(text="Owner-only commands are hidden.")
    await ctx.send(embed=embed)


@bot.command()
@commands.is_owner()
async def announce(ctx, *, message: str):
    channel = discord.utils.get(ctx.guild.channels, name=ANNOUNCEMENT_CHANNEL_NAME)
    if not channel: return await ctx.reply(f"I couldn't find the `#{ANNOUNCEMENT_CHANNEL_NAME}` channel.")
    embed = discord.Embed(title="📢 Announcement", description=message, color=discord.Color.blue(),
                          timestamp=datetime.datetime.now())
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    try:
        await channel.send(embed=embed);
        await ctx.message.add_reaction('✅')
    except discord.Forbidden:
        await ctx.reply(f"I don't have permission to send messages in {channel.mention}.")


@bot.command()
@commands.is_owner()
async def say(ctx, channel: discord.TextChannel, *, message: str):
    try:
        await channel.send(message);
        await ctx.message.add_reaction('✅')
    except discord.Forbidden:
        await ctx.reply(f"I don't have permission to send messages in {channel.mention}.")


@bot.command()
@commands.is_owner()
async def give(ctx, member: discord.Member, item_name: str, amount: int = 1):
    """Gives a user a specified amount of a material or crafted item."""
    author_id = str(member.id)
    normalized_item_name = item_name.replace("_", " ").title()

    if author_id not in user_armory:
        user_armory[author_id] = {"materials": {}, "crafted_items": {}}

    # Check if it's a material
    is_material = False
    for mat in MATERIALS:
        if mat["name"] == normalized_item_name:
            if "materials" not in user_armory[author_id]: user_armory[author_id]["materials"] = {}
            user_armory[author_id]["materials"][normalized_item_name] = user_armory[author_id]["materials"].get(
                normalized_item_name, 0) + amount
            is_material = True
            break

    # Check if it's a craftable item
    is_item = False
    if not is_material:
        if normalized_item_name in RECIPES:
            if "crafted_items" not in user_armory[author_id]: user_armory[author_id]["crafted_items"] = {}
            user_armory[author_id]["crafted_items"][normalized_item_name] = user_armory[author_id]["crafted_items"].get(
                normalized_item_name, 0) + amount
            is_item = True

    if not is_material and not is_item:
        return await ctx.reply(f"Could not find an item or material named `{normalized_item_name}`.")

    save_data(user_armory, ARMORY_FILE)
    await ctx.reply(f"Gave **{amount}x {normalized_item_name}** to {member.mention}.")


@bot.command()
@commands.cooldown(1, 300, commands.BucketType.default)
async def ping(ctx):
    ping_message = ("> PING: HENRY DAVIS DEFENSE ROBOT [ID: HD-DRX-0923]\n"
                    "> SIGNAL STRENGTH: MAX\n"
                    "> CRYPTO HANDSHAKE: VERIFIED ✅\n"
                    "> CORE TEMP: 37.6°C | STATUS: STABLE\n"
                    "> NEURAL INTERFACE: ONLINE\n"
                    "> TARGETING SYSTEMS: CALIBRATED\n"
                    "> DEFENSE SUBROUTINES: ARMED\n"
                    "> MOTION SERVOS: SYNCHRONIZED\n"
                    "> THREAT ASSESSMENT: STANDBY\n\n"
                    ">> RESPONSE RECEIVED <<\n\n"
                    "```diff\n"
                    "- [H.D.D.R]: SYSTEM ONLINE\n"
                    "- [H.D.D.R]: DIRECTIVE AWAITING\n"
                    "- [H.D.D.R]: HOSTILE DETECTION ENABLED\n"
                    "- [H.D.D.R]: “EMOS WILL BE ANNIHILATED.”\n"
                    "```\n"
                    "> END PING RESPONSE\n"
                    "> LOG CODE: 7B3F-A119-CX99")
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
        xp_reward = random.randint(5, 10);
        user_xp[author_id] = user_xp.get(author_id, 0) + xp_reward
        save_data(user_xp, XP_FILE);
        await check_and_update_roles(ctx.author)
        return await ctx.reply(f"Your patrol was uneventful. You secured the area and gained {xp_reward} XP.")
    embed = discord.Embed(title="Patrol Encounter!",
                          description="You've encountered a band of violent emos! They look hostile.",
                          color=discord.Color.dark_purple())
    embed.set_footer(text="What will you do?")
    view = PatrolEncounterView(ctx.author)
    message = await ctx.reply(embed=embed, view=view)
    await view.wait()
    for item in view.children: item.disabled = True
    await message.edit(view=view)
    if view.result in ("retreat", "timeout"):
        result_embed = discord.Embed(title="Patrol Ended", description="You chose to retreat, avoiding a risky fight.",
                                     color=discord.Color.light_grey())
        return await message.edit(embed=result_embed)
    if view.result == "attack":
        member_rank_weight = 1
        for rank_info in reversed(RANK_ROLES):
            for role in ctx.author.roles:
                if role.name == rank_info["name"]: member_rank_weight = rank_info["weight"]; break
            if member_rank_weight > 1: break
        win_chance = min(0.30 + (member_rank_weight * 0.05), 0.95)
        if random.random() < win_chance:
            xp_reward = random.randint(75, 150);
            user_xp[author_id] = user_xp.get(author_id, 0) + xp_reward
            save_data(user_xp, XP_FILE)
            stats = user_stats.get(author_id, {"patrol_wins": 0});
            stats["patrol_wins"] += 1
            user_stats[author_id] = stats;
            save_data(user_stats, STATS_FILE)
            if stats["patrol_wins"] >= 100:
                hunter_role = discord.utils.get(ctx.guild.roles, name=EMO_HUNTER_ROLE_NAME)
                if hunter_role and hunter_role not in ctx.author.roles:
                    await ctx.author.add_roles(hunter_role, reason="Achieved Emo Hunter status")
                    await ctx.send(
                        f"Congratulations, {ctx.author.mention}! For winning 100 patrol encounters, you have been awarded the **{EMO_HUNTER_ROLE_NAME}** role!")
            result_embed = discord.Embed(title="VICTORY!",
                                         description=f"You bravely fought and defeated the emos! You earned {xp_reward} XP for your valor.",
                                         color=discord.Color.green())
            await message.edit(embed=result_embed)
        else:
            result_embed = discord.Embed(title="DEFEAT!",
                                         description="The emos were stronger than they looked. You were defeated but managed to escape. You earned no XP.",
                                         color=discord.Color.red())
            await message.edit(embed=result_embed)


@bot.command()
async def scavenge(ctx):
    if not game_features_enabled: return
    author_id = str(ctx.author.id)
    current_time = datetime.datetime.now()
    if author_id in scavenge_cooldowns:
        if current_time - scavenge_cooldowns[author_id] < datetime.timedelta(minutes=5):
            return await ctx.reply("You've already picked this area clean. You can scavenge again in 5 minutes.")
    scavenge_cooldowns[author_id] = current_time
    if author_id not in user_armory:
        user_armory[author_id] = {"materials": {}, "crafted_items": {}}
    found_materials = {};
    materials_list = [m["name"] for m in MATERIALS];
    weights = [MATERIAL_RARITY_WEIGHTS[m["rarity"]] for m in MATERIALS]
    num_items_found = random.randint(2, 4)
    found_items = random.choices(materials_list, weights=weights, k=num_items_found)
    for item_name in found_items:
        found_materials[item_name] = found_materials.get(item_name, 0) + 1
        if "materials" not in user_armory[author_id]: user_armory[author_id]["materials"] = {}
        user_armory[author_id]["materials"][item_name] = user_armory[author_id]["materials"].get(item_name, 0) + 1
    save_data(user_armory, ARMORY_FILE)
    material_emojis = {m["name"]: m["emoji"] for m in MATERIALS}
    description = "\n".join(
        [f"{material_emojis[name]} **{name}** x{amount}" for name, amount in found_materials.items()])
    embed = discord.Embed(title="Scavenge Successful!", description=description, color=discord.Color.dark_green())
    embed.set_author(name=f"{ctx.author.display_name}'s Haul")
    embed.set_footer(text="Your findings have been added to your armory.")
    await ctx.reply(embed=embed)


@bot.command()
async def armory(ctx, member: discord.Member = None):
    if not game_features_enabled: return
    target_member = member or ctx.author
    view = ArmoryView(target_member)
    embed = await view.generate_embed()
    await ctx.reply(embed=embed, view=view)


@bot.command()
async def use(ctx, *, item_name: str):
    if not game_features_enabled: return
    global boss_hp
    author_id = str(ctx.author.id)
    if not boss_event_active:
        return await ctx.reply("There is no event active to use an item in.")
    normalized_item_name = item_name.strip().title()
    user_crafted_items = user_armory.get(author_id, {}).get("crafted_items", {})
    if user_crafted_items.get(normalized_item_name, 0) < 1:
        return await ctx.reply(f"You don't have any `{normalized_item_name}` to use.")
    if normalized_item_name == "Pipe Bomb":
        user_armory[author_id]["crafted_items"][normalized_item_name] -= 1
        save_data(user_armory, ARMORY_FILE)
        damage = random.randint(250, 400)
        boss_hp -= damage
        boss_participants.add(ctx.author.id)
        await ctx.send(
            f"💥 {ctx.author.mention} throws a **Pipe Bomb** at **{boss_title}**, dealing a massive **{damage}** damage!")
        if boss_event_message:
            original_embed = boss_event_message.embeds[0]
            original_embed.set_field_at(0, name="Health", value=create_health_bar(boss_hp, boss_max_hp), inline=False)
            await boss_event_message.edit(embed=original_embed)
    else:
        await ctx.reply(f"You can't use `{normalized_item_name}` right now.")


@bot.command()
@commands.is_owner()
async def worldboss(ctx, *, params: str):
    if not game_features_enabled: return
    global boss_event_active, boss_hp, boss_max_hp, boss_title, boss_participants, boss_event_message
    if boss_event_active: return await ctx.reply("A world boss event is already in progress.")
    try:
        title, description, health_str = [p.strip() for p in params.split('|')]
        health = int(health_str)
    except ValueError:
        return await ctx.reply("Invalid format. Use: `>worldboss Title | Description | Health`")
    boss_event_active = True;
    boss_hp = health;
    boss_max_hp = health
    boss_title = title;
    boss_participants = set()
    notification_role = discord.utils.get(ctx.guild.roles, name=NOTIFICATION_ROLE_NAME)
    if not notification_role:
        await ctx.reply(
            f"⚠️ **Warning:** Could not find the role `{NOTIFICATION_ROLE_NAME}`. The event will start without a ping.",
            delete_after=15)
        ping_message = ""
    else:
        ping_message = notification_role.mention
    embed = discord.Embed(title=f"🚨 WORLD BOSS EVENT! 🚨", description=description, color=discord.Color.magenta())
    embed.set_author(name=title)
    embed.add_field(name="Health", value=create_health_bar(boss_hp, boss_max_hp), inline=False)
    embed.add_field(name="Time Limit", value="60 seconds", inline=True)
    embed.add_field(name="How to Fight", value="Type `>hit` to attack!", inline=True)
    boss_event_message = await ctx.send(ping_message, embed=embed)
    await asyncio.sleep(60)
    await resolve_world_boss(ctx.channel)


@bot.command()
@commands.cooldown(1, 2, commands.BucketType.user)
async def hit(ctx):
    if not game_features_enabled: return
    global boss_event_active, boss_hp, boss_participants, boss_event_message
    if not boss_event_active:
        ctx.command.reset_cooldown(ctx)
        return
    boss_participants.add(ctx.author.id)
    member_rank_weight = 1
    for rank_info in reversed(RANK_ROLES):
        for role in ctx.author.roles:
            if role.name == rank_info["name"]: member_rank_weight = rank_info["weight"]; break
        if member_rank_weight > 1: break

    weapon_bonus = 0
    user_items = user_armory.get(str(ctx.author.id), {}).get("crafted_items", {})
    for item_name, recipe in RECIPES.items():
        if recipe.get("type") == "weapon" and user_items.get(item_name, 0) > 0:
            weapon_bonus = max(weapon_bonus, recipe.get("weight_bonus", 0))

    total_weight = member_rank_weight + weapon_bonus
    damage = (random.randint(5, 15) + total_weight) * 2
    boss_hp -= damage

    if boss_event_message:
        original_embed = boss_event_message.embeds[0]
        original_embed.set_field_at(0, name="Health", value=create_health_bar(boss_hp, boss_max_hp), inline=False)
        await boss_event_message.edit(embed=original_embed)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


@bot.command()
async def defend(ctx):
    if not game_features_enabled: return
    global attack_in_progress, defenders
    if not attack_in_progress: return await ctx.reply("There is no attack to defend against right now.",
                                                      delete_after=10)

    defenders.append(ctx.author.id)
    await ctx.message.add_reaction("🛡️")


@bot.command()
@commands.is_owner()
async def forceattack(ctx):
    if not game_features_enabled: return
    if attack_in_progress: return await ctx.reply("An attack is already in progress.")
    await ctx.reply("Forcing an attack now...");
    bot.loop.create_task(initiate_attack(ctx.channel))


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
    member_id = str(member.id);
    xp_amount = user_xp.get(member_id, 0)
    await ctx.reply(f"{member.display_name} has {xp_amount} XP.")


@bot.command()
@commands.is_owner()
async def setxp(ctx, member: discord.Member, amount: int):
    if not game_features_enabled: return
    member_id = str(member.id);
    user_xp[member_id] = amount;
    save_data(user_xp, XP_FILE)
    await check_and_update_roles(member)
    await ctx.reply(f"Set {member.mention}'s XP to {amount}.")


@bot.command()
@commands.is_owner()
async def addxp(ctx, member: discord.Member, amount: int):
    if not game_features_enabled: return
    member_id = str(member.id);
    user_xp[member_id] = user_xp.get(member_id, 0) + amount;
    save_data(user_xp, XP_FILE)
    await check_and_update_roles(member)
    await ctx.reply(f"Added {amount} XP to {member.mention}. They now have {user_xp[member_id]} XP.")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        if ctx.command.name == 'hit':
            try:
                await ctx.message.delete(delay=2)
            except discord.Forbidden:
                pass
            return
        await ctx.reply(f"This command is on cooldown. Please try again in {error.retry_after:.2f}s.")
    elif isinstance(error, commands.NotOwner):
        await ctx.reply("You do not have permission to use this command.")
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.reply(f"I could not find the channel you specified.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"You're missing a required argument for this command.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.reply("Unrecognized command. Use `>help` to see a list of available commands.")
    else:
        print(f"An unhandled error occurred: {error}")


bot.run(TOKEN)