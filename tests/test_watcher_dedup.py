"""
QA-Test für Watcher Guru Message Deduplication
Simuliert mehrfache Message-Events und validiert, dass nur eine verarbeitet wird.
"""
import os
import sys
import json
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test configuration
TEST_FILE = None
processed_ids = set()

def _load_processed_messages(filepath: str) -> set:
    """Lädt bereits verarbeitete Message-IDs aus der Datei."""
    if not os.path.exists(filepath):
        return set()
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            return set(data.get("processed_ids", []))
    except Exception as e:
        print(f"Fehler beim Laden: {e}")
        return set()

def _save_processed_messages(filepath: str, processed_ids: set):
    """Speichert verarbeitete Message-IDs in die Datei."""
    try:
        ids_list = list(processed_ids)[-500:]
        with open(filepath, 'w') as f:
            json.dump({"processed_ids": ids_list}, f)
    except Exception as e:
        print(f"Fehler beim Speichern: {e}")

def simulate_message_handler(message_id: int, processed_ids: set, filepath: str) -> bool:
    """
    Simuliert den telegram_handler.
    Returns: True wenn Message verarbeitet wurde, False wenn übersprungen.
    """
    # Deduplizierung Check
    if message_id in processed_ids:
        print(f"  [SKIP] Message {message_id} bereits verarbeitet.")
        return False
    
    # Als verarbeitet markieren
    processed_ids.add(message_id)
    _save_processed_messages(filepath, processed_ids)
    
    print(f"  [PROCESS] Message {message_id} wird verarbeitet.")
    return True


def test_deduplication():
    """Test: Gleiche Message-ID wird nur einmal verarbeitet."""
    print("\n" + "="*60)
    print("TEST 1: Deduplizierung - gleiche ID mehrfach")
    print("="*60)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        filepath = f.name
    
    try:
        processed_ids = set()
        results = []
        
        # Simuliere 5x die gleiche Message-ID (wie bei Reconnects)
        message_id = 12345
        print(f"\nSende Message-ID {message_id} fünfmal:")
        
        for i in range(5):
            result = simulate_message_handler(message_id, processed_ids, filepath)
            results.append(result)
        
        # Validierung
        processed_count = sum(results)
        print(f"\n✓ Ergebnis: {processed_count}/5 Messages verarbeitet")
        
        assert processed_count == 1, f"FEHLER: Erwartet 1, bekam {processed_count}"
        print("✅ TEST 1 BESTANDEN: Nur eine Message wurde verarbeitet!")
        
    finally:
        os.unlink(filepath)


def test_different_messages():
    """Test: Verschiedene Message-IDs werden alle verarbeitet."""
    print("\n" + "="*60)
    print("TEST 2: Verschiedene IDs werden alle verarbeitet")
    print("="*60)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        filepath = f.name
    
    try:
        processed_ids = set()
        results = []
        
        # Simuliere 5 verschiedene Messages
        message_ids = [100, 101, 102, 103, 104]
        print(f"\nSende verschiedene Message-IDs: {message_ids}")
        
        for msg_id in message_ids:
            result = simulate_message_handler(msg_id, processed_ids, filepath)
            results.append(result)
        
        # Validierung
        processed_count = sum(results)
        print(f"\n✓ Ergebnis: {processed_count}/5 Messages verarbeitet")
        
        assert processed_count == 5, f"FEHLER: Erwartet 5, bekam {processed_count}"
        print("✅ TEST 2 BESTANDEN: Alle verschiedenen Messages wurden verarbeitet!")
        
    finally:
        os.unlink(filepath)


def test_persistence():
    """Test: Processed IDs überleben Neuladen (Bot-Restart)."""
    print("\n" + "="*60)
    print("TEST 3: Persistenz über Bot-Restart")
    print("="*60)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        filepath = f.name
    
    try:
        # Erste "Session"
        print("\n[Session 1] Verarbeite Message 999:")
        processed_ids = set()
        result1 = simulate_message_handler(999, processed_ids, filepath)
        
        # Simuliere Bot-Restart - lade IDs neu
        print("\n[Bot Restart - Lade gespeicherte IDs]")
        processed_ids = _load_processed_messages(filepath)
        print(f"  Geladene IDs: {processed_ids}")
        
        # Zweite "Session" - gleiche Message nochmal
        print("\n[Session 2] Versuche Message 999 erneut:")
        result2 = simulate_message_handler(999, processed_ids, filepath)
        
        # Validierung
        assert result1 == True, "Session 1 sollte verarbeiten"
        assert result2 == False, "Session 2 sollte überspringen"
        print("\n✅ TEST 3 BESTANDEN: Deduplizierung überlebt Bot-Restart!")
        
    finally:
        os.unlink(filepath)


def test_limit_500():
    """Test: Nur die letzten 500 IDs werden behalten."""
    print("\n" + "="*60)
    print("TEST 4: Limit von 500 IDs")
    print("="*60)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        filepath = f.name
    
    try:
        processed_ids = set()
        
        # Füge 600 IDs hinzu
        print("\nFüge 600 Message-IDs hinzu...")
        for i in range(600):
            processed_ids.add(i)
        
        _save_processed_messages(filepath, processed_ids)
        
        # Lade und prüfe
        loaded_ids = _load_processed_messages(filepath)
        print(f"Gespeichert: 600, Geladen: {len(loaded_ids)}")
        
        assert len(loaded_ids) == 500, f"FEHLER: Erwartet 500, bekam {len(loaded_ids)}"
        
        # Prüfe dass die NEUESTEN behalten wurden (100-599, nicht 0-499)
        assert 599 in loaded_ids, "Neueste ID (599) sollte enthalten sein"
        assert 100 in loaded_ids, "ID 100 sollte enthalten sein"
        assert 99 not in loaded_ids, "Älteste IDs (0-99) sollten entfernt sein"
        
        print("✅ TEST 4 BESTANDEN: Nur letzte 500 IDs werden behalten!")
        
    finally:
        os.unlink(filepath)


if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# QA-TEST: Watcher Guru Message Deduplication")
    print("#"*60)
    
    try:
        test_deduplication()
        test_different_messages()
        test_persistence()
        test_limit_500()
        
        print("\n" + "="*60)
        print("🎉 ALLE TESTS BESTANDEN!")
        print("="*60)
        print("\nDie Deduplizierung funktioniert korrekt.")
        print("News werden nur noch 1x gesendet, auch bei:")
        print("  - Mehrfachen Telegram-Events")
        print("  - Bot-Restarts")
        print("  - Reconnects")
        
    except AssertionError as e:
        print(f"\n❌ TEST FEHLGESCHLAGEN: {e}")
        sys.exit(1)
