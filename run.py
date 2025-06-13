import discord
from discord.ext import commands
import asyncio
import logging
from shared import config
from bots.moderator_bot import setup_moderator
from bots.knowledge_bot import setup_knowledge_bot

# Logging-Konfiguration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

# Bot-Initialisierung mit den notwendigen Intents für beide Module
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logging.info(f'Bot {bot.user} ist online und einsatzbereit.')
    
    # Setze die Bot-Aktivität
    activity = discord.Activity(name="Tradingview", type=discord.ActivityType.watching)
    await bot.change_presence(activity=activity)
    logging.info(f"Bot-Status auf 'Watching Tradingview' gesetzt.")

    # Lade hier die spezifischen handler-funktionen
    logging.info("Lade Module...")
    bot.moderator_check = await setup_moderator(bot)
    bot.qna_check = await setup_knowledge_bot(bot)
    logging.info("Alle Module erfolgreich geladen und konfiguriert.")

@bot.event
async def on_message(message: discord.Message):
    # Ignoriere den Bot selbst und DMs
    if message.author == bot.user or message.guild is None:
        return

    # Priorität 1: Moderation. Wenn der Moderator die Nachricht behandelt, ist der Prozess beendet.
    moderation_handled = await bot.moderator_check(message)
    if moderation_handled:
        return

    # Priorität 2: Q&A.
    qna_handled = await bot.qna_check(message)
    if qna_handled:
        return
    
    # Wichtig: Falls wir später Prefix-Commands hinzufügen, muss dies am Ende stehen.
    await bot.process_commands(message)

async def main():
    async with bot:
        # Starte den Bot
        await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot wird heruntergefahren.")
    except ValueError as e:
        logging.critical(e)
