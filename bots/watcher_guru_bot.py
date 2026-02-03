import discord
from discord.ext import commands
from telethon import TelegramClient, events, types
import io
import asyncio
import logging
import os
import json

from shared import config, gemini_client, openai_client

# Configure logger
logger = logging.getLogger(__name__)

# Stelle sicher, dass das State-Verzeichnis existiert
os.makedirs(config.STATE_PATH, exist_ok=True)

# Initialize Telegram client
# We create a new client here because the shared one is not designed for persistent event listening.
SESSION_NAME = os.path.join(config.STATE_PATH, "watcher_guru_session")
PROCESSED_MESSAGES_FILE = os.path.join(config.STATE_PATH, "watcher_guru_processed.json")

tg_client = TelegramClient(
    SESSION_NAME,
    config.TELEGRAM_API_ID,
    config.TELEGRAM_API_HASH
)

# --- Deduplication: Track processed message IDs ---
# Lock für Thread-Safety bei concurrent access
_dedup_lock = asyncio.Lock()

def _load_processed_messages() -> set:
    """Lädt bereits verarbeitete Message-IDs aus der Datei."""
    if not os.path.exists(PROCESSED_MESSAGES_FILE):
        return set()
    try:
        with open(PROCESSED_MESSAGES_FILE, 'r') as f:
            data = json.load(f)
            if not isinstance(data, dict):
                logger.error("Invalid JSON structure in processed messages file")
                return set()
            return set(data.get("processed_ids", []))
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in processed messages: {e}")
        return set()
    except Exception as e:
        logger.error(f"Fehler beim Laden der processed messages: {e}")
        return set()

def _save_processed_messages(processed_ids: set):
    """Speichert verarbeitete Message-IDs in die Datei (trimmt auf 500)."""
    global processed_message_ids
    try:
        # Behalte nur die letzten 500 IDs (sortiert, um die neuesten zu behalten)
        ids_list = sorted(processed_ids)[-500:]
        # Aktualisiere auch das globale Set um Memory Leaks zu vermeiden
        processed_message_ids = set(ids_list)
        
        with open(PROCESSED_MESSAGES_FILE, 'w') as f:
            json.dump({"processed_ids": ids_list}, f)
    except Exception as e:
        logger.error(f"Fehler beim Speichern der processed messages: {e}")

# Global set für processed messages
processed_message_ids: set = _load_processed_messages()
_handler_registered = False  # Verhindert doppelte Handler-Registrierung

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
    global _handler_registered
    
    if _handler_registered:
        logger.warning("Watcher.Guru handler bereits registriert. Überspringe.")
        return
    
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
        global processed_message_ids
        raw_message = event.message
        message_id = raw_message.id
        
        # --- Thread-safe Deduplizierung ---
        async with _dedup_lock:
            if message_id in processed_message_ids:
                logger.info(f"Message {message_id} bereits verarbeitet. Überspringe.")
                return
            
            # Message als verarbeitet markieren BEVOR wir sie verarbeiten
            processed_message_ids.add(message_id)
            _save_processed_messages(processed_message_ids)
        
        logger.info(f"Received NEW message from Watcher.Guru. ID: {message_id}")
        
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
                    filename = f"watcher_guru_image_{message_id}.jpg"
                elif hasattr(raw_message.media, 'video'):
                    filename = f"watcher_guru_video_{message_id}.mp4"
                elif hasattr(raw_message.media, 'document') and hasattr(raw_message.file, 'name'):
                     filename = raw_message.file.name or f"document_{message_id}"

                discord_file = discord.File(fp=io.BytesIO(file_bytes), filename=filename)
                await channel.send(file=discord_file)
                logger.info(f"Forwarded media file '{filename}' to Discord.")

            except Exception as e:
                logger.error(f"Error processing media from Watcher.Guru: {e}")

    # Handler wurde erfolgreich registriert
    _handler_registered = True
    
    try:
        await tg_client.start(phone=lambda: config.TELEGRAM_PHONE)
        logger.info("Telegram client started for Watcher.Guru bot.")
        await tg_client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Error starting or running Telegram client for Watcher.Guru bot: {e}")
