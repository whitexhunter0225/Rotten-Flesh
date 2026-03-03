import discord
from discord.ext import commands, tasks
from discord import app_commands
import rblxopencloud
import os
import random
import logging
from dotenv import load_dotenv

# --- CONFIGURATION & SECURITY ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
ROBLOX_API_KEY = os.getenv('ROBLOX_API_KEY')
UNIVERSE_ID = int(os.getenv('UNIVERSE_ID', 0))
TICKET_CATEGORY_ID = int(os.getenv('TICKET_CATEGORY_ID', 0))
PLAYER_COUNT_VC = int(os.getenv('PLAYER_COUNT_VC', 0))

# --- LOGGING SETUP ---
# Generates clean, timestamped logs in your terminal instead of messy print statements
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RottenFlesh")

# --- ROBLOX API BRIDGE ---
experience = rblxopencloud.Experience(UNIVERSE_ID, api_key=ROBLOX_API_KEY)

# ==========================================
# UI COMPONENTS (PERSISTENT TICKET SYSTEM)
# ==========================================

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Timeout=None ensures the button works forever

    @discord.ui.button(label="🎫 Open Support Ticket", style=discord.ButtonStyle.blurple, custom_id="open_ticket_btn")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        
        if not category:
            return await interaction.response.send_message("Ticket category is not properly configured.", ephemeral=True)
            
        try:
            # Sets strict permissions so only the user and admins can see the ticket
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
            }
            channel = await guild.create_text_channel(
                name=f"ticket-{interaction.user.name}",
                category=category,
                overwrites=overwrites
            )
            await interaction.response.send_message(f"Ticket opened successfully: {channel.mention}", ephemeral=True)
            await channel.send(f"Welcome to **Brainrot Gacha** support, {interaction.user.mention}. Please describe your issue in detail.")
        except discord.Forbidden:
            await interaction.response.send_message("Rotten Flesh lacks permissions to create channels.", ephemeral=True)

# ==========================================
# MAIN BOT CLASS
# ==========================================

class RottenFlesh(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=discord.Intents.all())
        # The internal database for the Discord Gacha Simulator
        self.gacha_pool = {
            "Common": ["Rusted Bolt", "Plastic Soul", "Stale Bread"],
            "Rare": ["Digital Ghost", "Neon Battery", "Cyber-Core"],
            "Legendary": ["SIGMA OVERLORD", "VOID REAPER", "BRAINROT PRIMO"]
        }

    async def setup_hook(self):
        # 1. Load the persistent ticket button
        self.add_view(TicketView())
        
        # 2. Sync Slash Commands to Discord
        await self.tree.sync()
        logger.info("Slash commands synchronized successfully.")
        
        # 3. Start the live player counter background task
        if PLAYER_COUNT_VC != 0:
            self.live_stats.start()

    async def on_ready(self):
        logger.info(f"Rotten Flesh is online! Logged in as {self.user.name} ({self.user.id})")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Brainrot Gacha servers"))

    # --- LIVE PLAYER COUNTER TASK ---
    @tasks.loop(minutes=5)
    async def live_stats(self):
        try:
            info = experience.fetch_info()
            vc = self.get_channel(PLAYER_COUNT_VC)
            if vc and isinstance(vc, discord.VoiceChannel):
                await vc.edit(name=f"🟢 Playing: {info.playing}")
        except Exception as e:
            logger.error(f"Failed to update player count: {e}")

    @live_stats.before_loop
    async def before_live_stats(self):
        await self.wait_until_ready() # Ensures the bot is fully loaded before trying to rename channels

bot = RottenFlesh()

# ==========================================
# SLASH COMMANDS
# ==========================================

@bot.tree.command(name="spawn_ticket_panel", description="Admin: Spawns the support ticket button.")
@app_commands.default_permissions(administrator=True)
async def spawn_ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Official Support",
        description="Click the button below to open a private ticket with the moderation team.",
        color=discord.Color.dark_theme()
    )
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Panel spawned securely.", ephemeral=True)

@bot.tree.command(name="shout", description="Send a global message to all active Roblox servers.")
@app_commands.describe(message="The message to broadcast in-game")
@app_commands.default_permissions(administrator=True)
async def shout(interaction: discord.Interaction, message: str):
    try:
        experience.publish_message("GlobalAnnouncements", message)
        await interaction.response.send_message(f"📢 In-game shout successful:\n`{message}`", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Shout failed: {e}", ephemeral=True)

@bot.tree.command(name="gift_item", description="Inject a gacha item into a player's Roblox inventory.")
@app_commands.describe(roblox_id="The player's numeric Roblox User ID", item_name="Exact name of the item")
@app_commands.default_permissions(administrator=True)
async def gift_item(interaction: discord.Interaction, roblox_id: str, item_name: str):
    try:
        ds = experience.get_datastore("PlayerData")
        key = f"User_{roblox_id}"
        
        data, info = ds.get_entry(key)
        if data:
            inventory = data.get("Inventory", [])
            inventory.append(item_name)
            data["Inventory"] = inventory
            ds.set_entry(key, data)
            await interaction.response.send_message(f"🎁 Successfully gifted **{item_name}** to Roblox ID `{roblox_id}`.")
        else:
            await interaction.response.send_message("❌ User data not found in DataStore. They may need to join the game first.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ DataStore API Error: {e}", ephemeral=True)

@bot.tree.command(name="roll", description="Try your luck at the Discord Gacha Simulator!")
async def roll(interaction: discord.Interaction):
    chance = random.random()
    if chance < 0.03: # 3% Legendary Drop Rate
        rarity = "Legendary"
        color = discord.Color.gold()
    elif chance < 0.25: # 22% Rare Drop Rate
        rarity = "Rare"
        color = discord.Color.blue()
    else: # 75% Common Drop Rate
        rarity = "Common"
        color = discord.Color.light_grey()

    item = random.choice(bot.gacha_pool[rarity])
    
    embed = discord.Embed(title="🌀 Discord Gacha Pull", color=color)
    embed.add_field(name="Result", value=f"**{item}**")
    embed.add_field(name="Rarity", value=rarity)
    embed.set_footer(text="Join Brainrot Gacha on Roblox to keep it for real!")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clear", description="Bulk delete messages in the current channel.")
@app_commands.describe(amount="Number of messages to delete (max 100)")
@app_commands.default_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
    # Deferring is required for operations that might take longer than 3 seconds
    await interaction.response.defer(ephemeral=True) 
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🗑️ Rotten Flesh consumed {len(deleted)} messages.", ephemeral=True)

# ==========================================
# EXECUTION
# ==========================================

if __name__ == "__main__":
    if not TOKEN:
        logger.error("DISCORD_TOKEN is missing. Please check your .env file.")
    else:
        # log_handler=None prevents discord.py from overwriting our custom logger setup
        bot.run(TOKEN, log_handler=None) 
              
