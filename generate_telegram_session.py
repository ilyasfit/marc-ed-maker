import asyncio
from shared import config
from telethon import TelegramClient
import os

# Dieses Skript dient dazu, die .session-Datei interaktiv zu erstellen.
# Führen Sie es einmalig aus, bevor Sie den Bot starten.

SESSION_NAME = os.path.join(config.STATE_PATH, "telegram_session")

async def main():
    """
    Stellt eine interaktive Verbindung zu Telegram her, um die Session-Datei zu erstellen.
    """
    print("--- Telegram Session Generator ---")
    if not all([config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH]):
        print("FEHLER: TELEGRAM_API_ID und TELEGRAM_API_HASH nicht in der .env-Datei gefunden.")
        return

    # Stellen Sie sicher, dass das State-Verzeichnis existiert
    os.makedirs(config.STATE_PATH, exist_ok=True)

    print(f"Versuche, eine Session-Datei unter '{SESSION_NAME}.session' zu erstellen...")
    print("Telethon wird Sie nun nach Ihren Anmeldeinformationen fragen.")
    print("Die Telefonnummer wird aus der .env-Datei geladen.")
    print("Bitte geben Sie den von Telegram gesendeten Code und bei Aufforderung Ihr 2FA-Passwort ein.")

    client = TelegramClient(SESSION_NAME, int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH)

    def get_password():
        # Diese Funktion wird von Telethon nur aufgerufen, wenn ein Passwort benötigt wird.
        return config.TELEGRAM_PASSWORD

    try:
        # Wir verwenden client.start(), um den Anmeldevorgang zu initiieren.
        # Die Telefonnummer und das Passwort werden aus der Konfiguration bezogen.
        # Telethon wird interaktiv nach dem Code fragen, der an die Telefonnummer gesendet wird.
        await client.start(phone=config.TELEGRAM_PHONE, password=get_password)
        
        me = await client.get_me()
        if me:
            print(f"\nErfolgreich angemeldet als: {me.first_name} {me.last_name or ''} (@{me.username})")
            print(f"Die Session-Datei '{SESSION_NAME}.session' wurde erfolgreich erstellt/aktualisiert.")
            print("Sie können dieses Skript nun beenden (Strg+C) und den Hauptbot starten.")
        else:
            print("\nFEHLER: Konnte sich nicht erfolgreich anmelden. Bitte versuchen Sie es erneut.")

    except Exception as e:
        print(f"\nEin Fehler ist aufgetreten: {e}")
    finally:
        if client.is_connected():
            await client.disconnect()
        print("Verbindung getrennt.")

if __name__ == "__main__":
    # Verwenden Sie asyncio.run() in Python 3.7+
    # Für ältere Versionen: loop = asyncio.get_event_loop(); loop.run_until_complete(main())
    asyncio.run(main())
