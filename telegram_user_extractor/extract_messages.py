import asyncio
import os
import sys
from dotenv import load_dotenv
from telethon import TelegramClient

# --- Konfiguration & Setup ---

# Füge das Root-Verzeichnis des Hauptprojekts zum Python-Pfad hinzu
# Dies ermöglicht den Import von Modulen wie 'shared.config'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from shared import config as main_config

# Lade die spezifischen Umgebungsvariablen für dieses Skript
load_dotenv()

# Lade API-Daten und Session-Pfad aus der zentralen Konfiguration
API_ID = main_config.TELEGRAM_API_ID
API_HASH = main_config.TELEGRAM_API_HASH
# Wichtig: Telethon fügt die .session-Endung automatisch hinzu.
SESSION_FILE = os.path.join(main_config.STATE_PATH, "telegram_session")


# Lade Zieldaten aus der lokalen .env-Datei
CHANNEL_STR = os.getenv('TARGET_CHANNEL')
AUTHOR = os.getenv('TARGET_AUTHOR')


# --- Validierung ---

# Überprüfe, ob alle notwendigen Konfigurationen vorhanden sind
if not all([API_ID, API_HASH, SESSION_FILE, CHANNEL_STR, AUTHOR]):
    print("FEHLER: Konnte nicht alle Konfigurationen laden.")
    print("Stelle sicher, dass die .env-Datei im Root-Verzeichnis korrekt ist.")
    print("Überprüfe außerdem, ob TARGET_CHANNEL und TARGET_AUTHOR in 'telegram_user_extractor/.env' gesetzt sind.")
    sys.exit(1)

# Versuche, die Kanal-ID in eine Ganzzahl umzuwandeln.
# Telethon benötigt eine Ganzzahl für numerische IDs, ansonsten wird es als Username (String) behandelt.
try:
    CHANNEL = int(CHANNEL_STR)
except (ValueError, TypeError):
    CHANNEL = CHANNEL_STR # Behalte es als String, falls es ein Username ist

# --- Hauptfunktion ---

async def main():
    """
    Stellt eine Verbindung zu Telegram her, filtert Nachrichten eines bestimmten
    Autors in einem Kanal und speichert sie in einer Textdatei.
    """
    output_filename = f"extracted_messages_{AUTHOR}.txt"
    
    print(f"INFO: Starte den Nachrichten-Export für den Autor '{AUTHOR}' aus dem Kanal '{CHANNEL_STR}'.")
    print(f"INFO: Session-Datei wird von '{SESSION_FILE}.session' verwendet.")

    # Initialisiere den Telegram-Client mit der bestehenden Session-Datei
    async with TelegramClient(SESSION_FILE, int(API_ID), API_HASH) as client:
        
        print("INFO: Verbindung zu Telegram erfolgreich hergestellt.")
        
        messages_found = 0
        
        try:
            # Öffne die Zieldatei zum Schreiben
            with open(output_filename, "w", encoding="utf-8") as f:
                f.write(f"Nachrichten von '{AUTHOR}' aus dem Kanal '{CHANNEL_STR}'\n")
                f.write("="*50 + "\n\n")

                # Iteriere durch alle Nachrichten und filtere serverseitig
                async for msg in client.iter_messages(CHANNEL, from_user=AUTHOR):
                    messages_found += 1
                    # Formatiere die Nachricht für die Ausgabe
                    formatted_message = (
                        f"Nachricht ID: {msg.id}\n"
                        f"Datum: {msg.date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"Text:\n{msg.text or '[Kein Text oder nur Medieninhalt]'}\n"
                        f"{'-'*40}\n\n"
                    )
                    f.write(formatted_message)
                    
                    # Gib einen Fortschritt im Terminal aus
                    if messages_found % 50 == 0:
                        print(f"INFO: {messages_found} Nachrichten gefunden...")

        except Exception as e:
            print(f"FEHLER während des Exports: {e}")
            print("Mögliche Ursachen:")
            print("- Der angegebene Kanal oder Autor existiert nicht oder ist falsch geschrieben.")
            print("- Du hast keinen Zugriff auf den Kanal.")
            print("- Die Session-Datei ist ungültig oder abgelaufen.")
            return

    print("-" * 50)
    if messages_found > 0:
        print(f"✅ ERFOLG: {messages_found} Nachrichten wurden erfolgreich in die Datei '{output_filename}' exportiert.")
    else:
        print(f"INFO: Keine Nachrichten vom Autor '{AUTHOR}' im Kanal '{CHANNEL_STR}' gefunden.")
    print("-" * 50)


if __name__ == "__main__":
    # Führe die asynchrone Hauptfunktion aus
    asyncio.run(main())
