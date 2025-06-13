import sys
import os

# Füge das übergeordnete Verzeichnis zum Python-Pfad hinzu, um 'moderator' zu finden
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from moderator.filters import contains_forbidden_link

def run_filter_tests():
    print("\nFühre Filter-Tests aus...")
    
    whitelisted_domains = {'tradingview.com', 'google.com'}

    # Testfälle
    test_cases = {
        "Nachricht ohne Link": ("Hallo Welt", False),
        "Nachricht mit erlaubtem Link": ("Schaut euch das an: https://www.tradingview.com/chart/BTCUSDT", False),
        "Nachricht mit anderem erlaubtem Link": ("Google es: http://google.com", False),
        "Nachricht mit verbotenem Link": ("Kauft das hier: https://some-scam-site.com", True),
        "Nachricht mit gemischten Links (verbotener dabei)": ("Erlaubt ist tradingview.com, aber nicht http://bad-link.net", True),
        "Nachricht nur mit Text, der wie ein Link aussieht": ("Ich mag die Seite tradingview.com sehr.", False),
        "Nachricht mit komplexer URL und Pfad": ("Guter Link: https://de.tradingview.com/symbols/ETHUSDT/?exchange=BINANCE", False),
        "Nachricht nur mit Domain-Namen": ("Schaut auf google.com", False),
        "Nachricht nur mit verbotenem Domain-Namen": ("Schaut auf evil.com", True),
    }

    for name, (message, expected) in test_cases.items():
        result = contains_forbidden_link(message, whitelisted_domains)
        assert result == expected, f"Test fehlgeschlagen '{name}': Erwartet {expected}, aber bekam {result}"
        print(f"✓ Test bestanden: '{name}'")
    
    print("\nFilter-Tests erfolgreich bestanden.")

if __name__ == "__main__":
    run_filter_tests()
