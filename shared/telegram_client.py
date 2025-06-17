from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import Message
import asyncio
import os
from shared import config

SESSION_NAME = os.path.join(config.STATE_PATH, "telegram_session")

async def fetch_recent_messages(limit: int = 15) -> str | None:
    """
    Stellt eine Verbindung zu Telegram her, liest die letzten Nachrichten aus einem öffentlichen Kanal
    und gibt deren Textinhalte als zusammenhängenden String zurück.
    """
    if not all([config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH, config.TELEGRAM_CHANNEL_USERNAME]):
        print("FEHLER: Telegram API-Konfigurationen sind unvollständig.")
        return None

    client = TelegramClient(SESSION_NAME, int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH)
    
    try:
        await client.connect()
        print(f"INFO: Mit Telegram verbunden. Lese Kanal: {config.TELEGRAM_CHANNEL_USERNAME}")
        
        messages = await client.get_messages(config.TELEGRAM_CHANNEL_USERNAME, limit=limit)
        
        text_contents = []
        for message in reversed(messages):  # Umkehren für chronologische Reihenfolge
            if message and isinstance(message, Message) and message.text and not message.text.isspace():
                text_contents.append(message.text)
        
        if not text_contents:
            print("INFO: Keine neuen Textnachrichten im Telegram-Kanal gefunden.")
            return None
            
        print(f"INFO: {len(text_contents)} Textnachrichten aus Telegram extrahiert.")
        return "\n\n---\n\n".join(text_contents)

    except Exception as e:
        print(f"FEHLER beim Abrufen von Telegram-Nachrichten: {e}")
        return None
    finally:
        if client.is_connected():
            await client.disconnect()
            print("INFO: Verbindung zu Telegram getrennt.")
