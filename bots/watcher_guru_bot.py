import discord
from discord.ext import commands
from telethon import TelegramClient, events, types
import io
import asyncio
import logging
import os

from shared import config, gemini_client, openai_client

# Configure logger
logger = logging.getLogger(__name__)

# Initialize Telegram client
# We create a new client here because the shared one is not designed for persistent event listening.
SESSION_NAME = os.path.join(config.STATE_PATH, "watcher_guru_session")
tg_client = TelegramClient(
    SESSION_NAME,
    config.TELEGRAM_API_ID,
    config.TELEGRAM_API_HASH
)

async def reformat_message(message_text: str) -> str:
    """
    Reformats the news message using the Gemini API with a specific prompt.
    """
    news = message_text.split('\n')[0].strip()

    prompt = f"""
    Teile die Nachricht, die in den eckigen Klammern eingebettet ist. 
    Deine Mitteilung beinhaltet einen Witz oder eine lustige Bemerkung über deine Vorliebe zum Dressurreiten, erwähne das Dressurreiten jedoch maximal ein Mal! 
    Deine Mitteilungen sollten fachkundig und präzise sein, aber auch eine charmante Note haben, die deine Liebe zum Dressurreiten zeigt. 
    Hier sind einige Beispiele, wie du deine Mitteilungen gestalten kannst, um eine gute Verbindung zwischen aktuellen Ereignissen und Dressurreiten herzustellen: 

    Zuerst teilst du die Nachricht, dann machst du eine humorvolle Bemerkung / Kommentar (mit deinem Dressurreiter-Jargon) über die News im Kontext auf den Kryptomarkt.

    So sieht dein Nachrichtenformat aus:

    "## :rotating_light: **Aufgepasst Kameraden!** :rotating_light: \n\n > (hier fügst du die Nachricht ein, lasse das "JUST IN" oder "BREAKING" aus und übersetze sie auf deutsch) \n\n (hier fügst du deinen Kommentar ein)"
    In den Klammern ist die Anweisung, was du wo und wie einfügen sollst.
    
    Hier sind 3 Beispiele, wie du eine News gestalten kannst:

    "## :rotating_light: **Achtung Kameraden!** :rotating_light: \n\n
    > Elon Musk sagt, er unterstützt Präsident Donald Trump voll und ganz nach dem Angriff während der Kundgebung.\n\n

    Das ist ja fast so aufregend wie ein Dressurwettbewerb bei den Olympischen Spielen! Ob die Märkte jetzt einen eleganten Galopp oder eine wilde Buckelshow hinlegen?"

    "## :rotating_light: **Es gibt Neuigkeiten!** :rotating_light: \n\n
> Elon Musk sagt, er unterstützt Präsident Donald Trump voll und ganz nach dem Angriff während der Kundgebung.\n\n

Ah, das ist so klassisch wie eine Dressurkür! Wird der Kryptomarkt eine elegante Pirouette drehen oder über die Hürden stolpern?"

"## :rotating_light: **Sattelt auf Kameraden!** :rotating_light: \n\n
> Elon Musk sagt, er unterstützt Präsident Donald Trump voll und ganz nach dem Angriff während der Kundgebung. \n\n

Wie bei einem guten Dressurtraining ist es wichtig, auf Details zu achten. Wird der Kryptomarkt jetzt im Einklang traben oder aus dem Sattel geworfen werden?"

Achte darauf, dass dein Kommentar zum Kontext passt und humorvoll zu deinem Charakter passt!
    
    
    Bette die Mitteilung nicht in Anführungszeichen ein. Du teilst nur Nachrichten, die relevant und wichtig sind. Du machst die Anspielung (in Bezug auf das Reiten & Dressur) maximal ein Mal pro Mitteilung! 
    
    Die Nachricht: [{news}]
    """

    # Use the configured LLM provider
    user_query = "Formuliere die Nachricht um."
    
    if config.LLM_PROVIDER.lower() == 'gemini':
        return await gemini_client.get_gemini_response(
            user_query=user_query,
            context_data="",
            system_instruction_override=prompt
        )
    else:
        # Default to OpenAI
        if config.OPENAI_API_KEY:
            return await openai_client.get_openai_response(
                user_query=user_query,
                context_data="",
                system_instruction_override=prompt
            )
        elif config.GEMINI_API_KEY:
             logger.warning("OpenAI configured but no key found. Falling back to Gemini.")
             return await gemini_client.get_gemini_response(
                user_query=user_query,
                context_data="",
                system_instruction_override=prompt
            )
        else:
             logger.error("No valid LLM provider configured.")
             return f"Fehler: Konnte Nachricht nicht umformulieren. (Kein LLM)"


async def start_watcher_guru_bot(bot: commands.Bot):
    """
    Starts the Telegram client to listen for messages from the Watcher.Guru channel
    and forwards them to a specific Discord channel.
    """
    if not all([config.WATCHER_GURU_DISCORD_CHANNEL_ID, config.WATCHER_GURU_TELEGRAM_USERNAME, config.TELEGRAM_PHONE]):
        logger.warning("Watcher.Guru bot is not configured. Skipping.")
        return

    await bot.wait_until_ready()
    channel = bot.get_channel(config.WATCHER_GURU_DISCORD_CHANNEL_ID)
    if not channel:
        logger.error(f"Could not find Discord channel with ID {config.WATCHER_GURU_DISCORD_CHANNEL_ID} for Watcher.Guru bot.")
        return

    logger.info(f"Watcher.Guru bot is ready. Forwarding from '{config.WATCHER_GURU_TELEGRAM_USERNAME}' to Discord channel '{channel.name}'.")

    @tg_client.on(events.NewMessage(chats=config.WATCHER_GURU_TELEGRAM_USERNAME))
    async def telegram_handler(event):
        raw_message = event.message
        logger.info(f"Received message from Watcher.Guru. ID: {raw_message.id}")
        
        # Process text content first
        if raw_message.text:
            try:
                message = await reformat_message(raw_message.text)
                await channel.send(message)
            except Exception as e:
                logger.error(f"Error processing text message from Watcher.Guru: {e}")

        # Check for media attachments and forward them
        if raw_message.media:
            try:
                # Download the media file into memory
                file_bytes = await tg_client.download_media(raw_message.media, file=bytes)
                
                filename = "media"
                if hasattr(raw_message.media, 'photo'):
                    filename = f"watcher_guru_image_{raw_message.id}.jpg"
                elif hasattr(raw_message.media, 'video'):
                    filename = f"watcher_guru_video_{raw_message.id}.mp4"
                elif hasattr(raw_message.media, 'document') and hasattr(raw_message.file, 'name'):
                     filename = raw_message.file.name or f"document_{raw_message.id}"

                discord_file = discord.File(fp=io.BytesIO(file_bytes), filename=filename)
                await channel.send(file=discord_file)
                logger.info(f"Forwarded media file '{filename}' to Discord.")

            except Exception as e:
                logger.error(f"Error processing media from Watcher.Guru: {e}")

    try:
        await tg_client.start(phone=lambda: config.TELEGRAM_PHONE)
        logger.info("Telegram client started for Watcher.Guru bot.")
        await tg_client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Error starting or running Telegram client for Watcher.Guru bot: {e}")
