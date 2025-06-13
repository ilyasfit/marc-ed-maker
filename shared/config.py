import os
from dotenv import load_dotenv

# Lade .env aus dem Root-Verzeichnis (zwei Ebenen über 'shared/')
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

# Discord & General Config
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
HUGO_DISCORD_ID = int(os.getenv('HUGO_DISCORD_ID', 0))

# Q&A Bot (Bits) Config
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_SYSTEM_INSTRUCTION = os.getenv('GEMINI_SYSTEM_INSTRUCTION')

_raw_qna_channel_ids = os.getenv("QNA_TARGET_CHANNEL_IDS", "")
QNA_TARGET_CHANNEL_IDS = []
if _raw_qna_channel_ids:
    try:
        QNA_TARGET_CHANNEL_IDS = [int(id_str.strip()) for id_str in _raw_qna_channel_ids.split(',') if id_str.strip()]
    except ValueError:
        print("FEHLER: QNA_TARGET_CHANNEL_IDS konnten nicht geparsed werden.")

# Pfade (zentral definiert für einfache Wartung)
BASE_DIR = os.path.dirname(dotenv_path)
MODERATOR_RULES_PATH = os.path.join(BASE_DIR, 'knowledge', 'moderator_rules')
QNA_CONTEXT_PATH = os.path.join(BASE_DIR, 'knowledge', 'qna_context')

# Validierung kritischer Konfigurationen
if not DISCORD_TOKEN:
    raise ValueError("Kritischer Fehler: DISCORD_TOKEN nicht in .env gefunden!")
if not HUGO_DISCORD_ID:
    raise ValueError("Kritischer Fehler: HUGO_DISCORD_ID nicht in .env gefunden!")
