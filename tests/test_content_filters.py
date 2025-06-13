import sys
import os
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from moderator.filters import find_forbidden_content

def run_content_filter_tests():
    print("\nFühre Content-Filter-Tests aus...")
    
    forbidden_words = {"puta", "filho da puta", "esquema"}
    seed_patterns = {r"(\b[a-zA-Z]+\b\s){11}\b[a-zA-Z]+\b"}

    test_cases = {
        "Saubere Nachricht": ("Olá, como vai você?", None),
        "Einzelnes verbotenes Wort": ("Não seja uma puta.", "Uso de linguagem/tópico proibido"),
        "Verbotenes Wort (Großbuchstaben)": ("Isso é PUTA besteira.", "Uso de linguagem/tópico proibido"),
        "Mehrteilige Phrase": ("Ele é um filho da puta.", "Uso de linguagem/tópico proibido"),
        "Potenzielle Seedphrase (12 Wörter)": ("apple banana car dog eleven frog grass house ice juice king lamp", "Potenzielle Seedphrase gefunden"),
        "Seedphrase mit Satzzeichen": ("my seed is: apple banana car dog eleven frog grass house ice juice king lamp.", "Potenzielle Seedphrase gefunden"),
        "Zu kurze Phrase (11 Wörter)": ("apple banana car dog eleven frog grass house ice juice king", None),
        "Wort, das verbotenes Wort enthält": ("Este computador é potente.", None),
    }

    for name, (message, expected) in test_cases.items():
        result = find_forbidden_content(message, forbidden_words, seed_patterns)
        assert result == expected, f"Test fehlgeschlagen '{name}': Erwartet {expected}, aber bekam {result}"
        print(f"✓ Test bestanden: '{name}'")
    
    print("\nContent-Filter-Tests erfolgreich bestanden.")

if __name__ == "__main__":
    run_content_filter_tests()
