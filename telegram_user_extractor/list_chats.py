import asyncio
import os
import sys
from telethon import TelegramClient

# --- Konfiguration & Setup ---

# Füge das Root-Verzeichnis des Hauptprojekts zum Python-Pfad hinzu
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from shared import config as main_config

# Lade API-Daten und Session-Pfad aus der zentralen Konfiguration
API_ID = main_config.TELEGRAM_API_ID
API_HASH = main_config.TELEGRAM_API_HASH
SESSION_FILE = os.path.join(main_config.STATE_PATH, "telegram_session")

# --- Validierung ---
if not all([API_ID, API_HASH, SESSION_FILE]):
    print("FEHLER: Konnte die Hauptkonfiguration nicht laden.")
    sys.exit(1)

# --- Hauptfunktion ---

async def main():
    """
    Listet alle Dialoge (Chats, Kanäle, Gruppen) auf, auf die der
    Benutzer Zugriff hat, und zeigt deren Namen und IDs an.
    """
    print("INFO: Verbinde mit Telegram, um Chat-Liste abzurufen...")
    
    async with TelegramClient(SESSION_FILE, int(API_ID), API_HASH) as client:
        print("INFO: Verbindung erfolgreich. Lade Dialoge...")
        print("-" * 50)
        print("{:<15} | {}".format("Chat ID", "Chat Name"))
        print("-" * 50)
        
        async for dialog in client.iter_dialogs():
            # Gib den Namen und die ID für jeden Chat aus
            print("{:<15} | {}".format(dialog.id, dialog.name))
            
        print("-" * 50)
        print("INFO: Liste vollständig.")
        print("\nAnleitung:")
        print("1. Finde den gewünschten privaten Kanal in der Liste oben.")
        print("2. Kopiere die numerische 'Chat ID' (inklusive des Minuszeichens, falls vorhanden).")
        print("3. Füge diese ID in die 'TARGET_CHANNEL'-Variable in der '.env'-Datei ein.")

if __name__ == "__main__":
    asyncio.run(main())
