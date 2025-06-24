import sys
import os
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from moderator.filters import find_forbidden_content

def run_content_filter_tests():
    print("\nFühre Content-Filter-Tests aus...")
    
    forbidden_words = {"hure", "hurensohn", "schneeballsystem"}
    seed_patterns = {r"(\b[a-zA-Z]+\b\s){11}\b[a-zA-Z]+\b"}

    test_cases = {
        "Saubere Nachricht": ("Hallo, wie geht es Ihnen?", None),
        "Einzelnes verbotenes Wort": ("Sei keine Hure.", "Nutzung von verbotener Sprache/Thema"),
        "Verbotenes Wort (Großbuchstaben)": ("Das ist HUREN-Unsinn.", "Nutzung von verbotener Sprache/Thema"),
        "Mehrteilige Phrase": ("Er ist ein Hurensohn.", "Nutzung von verbotener Sprache/Thema"),
        "Potenzielle Seedphrase (12 Wörter)": ("Apfel Banane Auto Hund elf Frosch Gras Haus Eis Saft König Lampe", "Potenzielle Seedphrase gefunden"),
        "Seedphrase mit Satzzeichen": ("Mein Seed ist: Apfel Banane Auto Hund elf Frosch Gras Haus Eis Saft König Lampe.", "Potenzielle Seedphrase gefunden"),
        "Zu kurze Phrase (11 Wörter)": ("Apfel Banane Auto Hund elf Frosch Gras Haus Eis Saft König", None),
        "Wort, das verbotenes Wort enthält": ("Dieser Computer ist leistungsstark.", None),
    }

    for name, (message, expected) in test_cases.items():
        result = find_forbidden_content(message, forbidden_words, seed_patterns)
        assert result == expected, f"Test fehlgeschlagen '{name}': Erwartet {expected}, aber bekam {result}"
        print(f"✓ Test bestanden: '{name}'")
    
    print("\nContent-Filter-Tests erfolgreich bestanden.")

if __name__ == "__main__":
    run_content_filter_tests()
