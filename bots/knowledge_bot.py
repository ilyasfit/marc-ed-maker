# bots/knowledge_bot.py
import discord
from shared import config, gemini_client
import os

def load_context_data():
    """
    Lädt rekursiv alle .txt- und .md-Dateien aus dem QNA_CONTEXT_PATH
    und gibt deren kombinierten Inhalt als einzelnen String zurück.
    """
    combined_parts = []
    if not os.path.isdir(config.QNA_CONTEXT_PATH):
        print(f"WARNUNG: Q&A-Kontextverzeichnis nicht gefunden: {config.QNA_CONTEXT_PATH}")
        return ""
    
    # os.walk durchläuft das Verzeichnis und alle seine Unterverzeichnisse
    for root, _, files in sorted(os.walk(config.QNA_CONTEXT_PATH)):
        for filename in sorted(files):  # Sortiere Dateien in jedem Verzeichnis für Konsistenz
            if filename.endswith((".txt", ".md")):
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        combined_parts.append(f.read())
                except Exception as e:
                    print(f"FEHLER: Konnte die Kontextdatei nicht lesen: {filepath} - {e}")
                    
    return "\n\n---\n\n".join(combined_parts)

async def handle_qna_mention(message: discord.Message, bot_user: discord.ClientUser):
    # Prüfen, ob die Bedingungen für den Q&A-Bot erfüllt sind
    is_target_channel = not config.QNA_TARGET_CHANNEL_IDS or message.channel.id in config.QNA_TARGET_CHANNEL_IDS
    bot_mentioned = bot_user.mentioned_in(message)

    if not (is_target_channel and bot_mentioned):
        return False # Nicht für uns, gib False zurück

    async with message.channel.typing():
        # Extrahiere die Anfrage
        query = message.content.replace(f'<@{bot_user.id}>', '').strip()
        
        # Lade Kontext
        context = load_context_data()

        # Rufe Gemini auf
        response = await gemini_client.get_gemini_response(query, context)

        # Sende Antwort und teile sie bei Bedarf auf, um das 2000-Zeichen-Limit von Discord einzuhalten
        is_first_message = True
        # Teile die Antwort in 2000-Zeichen-Blöcke auf
        for i in range(0, len(response), 2000):
            chunk = response[i:i+2000]
            if is_first_message:
                # Die erste Nachricht wird als direkte Antwort gesendet
                await message.reply(chunk)
                is_first_message = False
            else:
                # Nachfolgende Nachrichten werden einfach in den Kanal gesendet
                await message.channel.send(chunk)
    
    return True # Wir haben die Nachricht verarbeitet

async def setup_knowledge_bot(bot):
    # Diese Funktion gibt die Handler-Funktion zurück, damit sie in run.py als Checker verwendet werden kann.
    print("Knowledge-Bot-Modul erfolgreich geladen.")
    # Wir übergeben den bot.user direkt, um den API-Aufruf im Handler zu vereinfachen
    async def qna_check(message: discord.Message):
        return await handle_qna_mention(message, bot.user)
    
    return qna_check
