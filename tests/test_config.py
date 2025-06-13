import os
import sys
from dotenv import load_dotenv

def run_config_test():
    print("Führe Konfigurationstest aus...")
    
    # Stelle sicher, dass der Pfad zur .env-Datei korrekt ist
    # Gehe ein Verzeichnis hoch von /tests
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    
    if not os.path.exists(env_path):
        print(f"FEHLER: .env-Datei nicht gefunden unter {os.path.abspath(env_path)}")
        sys.exit(1)

    load_dotenv(dotenv_path=env_path)

    token = os.getenv('DISCORD_TOKEN')
    hugo_id = os.getenv('HUGO_DISCORD_ID')

    assert token is not None, "Test fehlgeschlagen: DISCORD_TOKEN ist None."
    assert len(token) > 50, "Test fehlgeschlagen: DISCORD_TOKEN scheint ungültig zu sein."
    print("✓ DISCORD_TOKEN wurde erfolgreich geladen.")
    
    assert hugo_id is not None, "Test fehlgeschlagen: HUGO_DISCORD_ID ist None."
    assert hugo_id == "294552900653285376", f"Test fehlgeschlagen: HUGO_DISCORD_ID ist '{hugo_id}', erwartet wurde '294552900653285376'."
    print("✓ HUGO_DISCORD_ID wurde erfolgreich geladen.")

    print("\nKonfigurationstest erfolgreich bestanden.")

if __name__ == "__main__":
    run_config_test()
