import discord
from discord.ext import commands
import asyncio
import logging
from shared import config
from bots.moderator_bot import setup_moderator
from bots.knowledge_bot import setup_knowledge_bot
from bots.engagement_bot import setup_engagement

# Logging-Konfiguration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

# Bot-Initialisierung mit den notwendigen Intents
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logging.info(f'Bot {bot.user} ist online und einsatzbereit.')
    activity = discord.Activity(name="oraculobitvision", type=discord.ActivityType.watching)
    await bot.change_presence(activity=activity)
    logging.info(f"Bot-Status auf 'Watching oraculobitvision' gesetzt.")

async def setup_cogs(bot):
    logging.info("Lade Module...")
    await setup_moderator(bot)
    await setup_knowledge_bot(bot)
    await setup_engagement(bot)
    logging.info("Alle Module erfolgreich geladen.")

async def main():
    await setup_cogs(bot)
    await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot wird heruntergefahren.")
    except Exception as e:
        logging.critical(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
