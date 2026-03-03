import discord
from discord.ext import commands, tasks
from discord import app_commands
import rblxopencloud
import os
import random
import logging
from dotenv import load_dotenv

# Load Local Environment (Railway handles this automatically in production)
load_dotenv()

# --- SECURITY CONSTANTS ---
TOKEN = os.getenv('DISCORD_TOKEN')
ROBLOX_API_KEY = os.getenv('ROBLOX_API_KEY')
UNIVERSE_ID = os.getenv('UNIVERSE_ID')
TICKET_CATEGORY_ID = os.getenv('TICKET_CATEGORY_ID')
PLAYER_COUNT_VC = os.getenv('PLAYER_COUNT_VC')

# Validate variables to prevent silent crashes on deployment
if not all([TOKEN, ROBLOX_API_KEY, UNIVERSE_ID, TICKET_CATEGORY_ID, PLAYER_COUNT_VC]):
    raise ValueError("Missing critical environment variables! Check your Railway variables tab.")

UNIVERSE_ID = int(UNIVERSE_ID)
TICKET_CATEGORY_ID = int(TICKET_CATEGORY_ID)
PLAYER_COUNT_VC = int(PLAYER_COUNT_VC)

# --- PROFESSIONAL LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger("RottenFlesh")

# --- ROBLOX CLOUD CONNECTION ---
experience = rblxopencloud.Experience(UNIVERSE_ID, api_key=ROBLOX_API_KEY)

# ==========================================
# INTERACTIVE UI (TICKETS)
# ==========================================

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) 

    @discord.ui.button(label="🎫 Open Support Ticket", style=discord.ButtonStyle.blurple, custom_id="persistent_ticket_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        
        if not category:
            return await interaction.response.send_message("Ticket system misconfigured. Category missing.", ephemeral=True)
            
        try:
            # Create a private channel
            channel = await guild.create_text_channel(
                name=f"ticket-{interaction.user.name}",
                category=category,
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                }
            )
            await interaction.response.send_message(f"Your private support line is ready: {channel.mention}", ephemeral=True)
            await channel.send(f"Welcome {interaction.user.mention}. Please drop a screenshot and description of your bug or issue.")
        except discord.Forbidden:
            await interaction.response.send_message("I lack the 'Manage Channels' permission required to open a ticket.", ephemeral=True)
            logger.error(f"Failed to create ticket for {interaction.user.name}: Missing Permissions")

# ==========================================
# BOT CORE CLASS
# ==========================================

class RottenFlesh(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=discord.Intents.all(), help_command=None)
        
        self.gacha_pool = {
            "Common": ["Rusted Bolt", "Plastic Soul"],
            "Rare": ["Digital Ghost", "Neon Battery"],
            "Legendary": ["SIGMA OVERLORD", "VOID REAPER"]
        }

    async def setup_hook(self):
        # 1. Register persistent UI
        self.add_view(TicketView())
        # 2. Sync slash commands globally
        await self.tree.sync()
        logger.info("Global slash commands synchronized.")
        # 3. Start background tasks
        self.live_stats.start()

    async def on_ready(self):
        logger.info(f"Identity confirmed: {self.user.name} (ID: {self.user.id})")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="over Brainrot Gacha"))

    # --- LIVE DATA TASK ---
    @tasks.loop(minutes=6) # 6 minutes to avoid rate-limiting on shared Railway IPs
    async def live_stats(self):
        try:
            info = experience.fetch_info()
            vc = self.get_channel(PLAYER_COUNT_VC)
            if vc:
                await vc.edit(name=f"🟢 Playing: {info.playing}")
        except Exception as e:
            logger.warning(f"Roblox API Sync Error: {e}")

    @live_stats.before_loop
    async def before_live_stats(self):
        await self.wait_until_ready()

bot = RottenFlesh()

# ==========================================
# SLASH COMMANDS
# ==========================================

@bot.tree.command(name="spawn_ticket_panel", description="Admin: Spawns the support ticket button.")
@app_commands.default_permissions(administrator=True)
async def spawn_ticket_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Brainrot Gacha Support",
        description="Click below to open a private ticket with our moderation and development team.",
        color=0x2b2d31 # Discord's dark gray hex color
    )
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Panel deployed.", ephemeral=True)

@bot.tree.command(name="shout", description="Broadcast a global message to all active Roblox servers.")
@app_commands.describe(message="The message to display in-game")
@app_commands.default_permissions(administrator=True)
async def shout(interaction: discord.Interaction, message: str):
    await interaction.response.defer(ephemeral=True) # Prevent timeout while API is called
    try:
        experience.publish_message("GlobalAnnouncements", message)
        await interaction.followup.send(f"📢 In-game broadcast sent:\n`{message}`")
    except Exception as e:
        await interaction.followup.send(f"❌ Broadcast failed: {e}")

@bot.tree.command(name="gift_item", description="Inject a gacha item into a player's Roblox inventory.")
@app_commands.describe(roblox_id="The player's numeric Roblox ID", item_name="Exact name of the item")
@app_commands.default_permissions(administrator=True)
async def gift_item(interaction: discord.Interaction, roblox_id: str, item_name: str):
    await interaction.response.defer() 
    try:
        ds = experience.get_datastore("PlayerData")
        key = f"User_{roblox_id}"
        
        data, info = ds.get_entry(key)
        if data:
            inventory = data.get("Inventory", [])
            inventory.append(item_name)
            data["Inventory"] = inventory
            ds.set_entry(key, data)
            await interaction.followup.send(f"🎁 Injected **{item_name}** into Roblox ID `{roblox_id}`.")
        else:
            await interaction.followup.send("❌ User DataStore not found. They must join the game at least once.")
    except Exception as e:
        await interaction.followup.send(f"❌ API Error: {e}")

@bot.tree.command(name="roll", description="Try your luck at the Discord Gacha Simulator!")
async def roll(interaction: discord.Interaction):
    chance = random.random()
    if chance < 0.05: # 5%
        rarity = "Legendary"
        color = discord.Color.gold()
    elif chance < 0.25: # 20%
        rarity = "Rare"
        color = discord.Color.blue()
    else: # 75%
        rarity = "Common"
        color = discord.Color.light_grey()

    item = random.choice(bot.gacha_pool[rarity])
    
    embed = discord.Embed(title="🌀 Discord Gacha", color=color)
    embed.add_field(name="Result", value=f"**{item}**")
    embed.add_field(name="Rarity", value=rarity)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clear", description="Bulk delete messages in the current channel.")
@app_commands.describe(amount="Number of messages to delete (1-100)")
@app_commands.default_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
    await interaction.response.defer(ephemeral=True) 
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🗑️ Consumed {len(deleted)} messages.")

# ==========================================
# BOOT SEQUENCE
# ==========================================

if __name__ == "__main__":
    # The 'log_handler=None' prevents duplicate logs in the Railway console
    bot.run(TOKEN, log_handler=None) 
