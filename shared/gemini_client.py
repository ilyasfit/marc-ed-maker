# shared/gemini_client.py
import google.generativeai as genai
from google.generativeai import types
import logging
from shared import config # NEUER IMPORT
import asyncio

# Ensure logger is configured if this module is run standalone or if not configured by a higher level script
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(module)s - %(message)s')


# Konfiguriere den Gemini Client global, wenn das Modul geladen wird
# Dies ist sicherer, falls der Key während der Laufzeit nicht verfügbar wird
if config.GEMINI_API_KEY:
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        logging.info("Gemini API Client configured successfully.")
    except Exception as e:
        logging.critical(f"Kritischer Fehler bei der Konfiguration des Gemini Clients: {e}. Der Bot kann möglicherweise keine Antworten generieren.")
else:
    logging.warning("Kein Gemini API Key in der Konfiguration gefunden. Gemini-Funktionalität ist deaktiviert.")

GEMINI_MODEL_NAME = "gemini-2.0-flash" # Aktualisiert per Nutzeranweisung

async def get_gemini_response(user_query: str, context_data: str) -> str:
    """
    Sendet eine Anfrage an die Gemini API und gibt die Textantwort zurück.
    Kombiniert System-Instruktion, Kontextdaten und Nutzeranfrage.
    Nutzt asynchrone Aufrufe für bessere Performance im Discord Bot.
    """
    if not config.GEMINI_API_KEY:
        logging.error("Versuch, Gemini ohne API Key aufzurufen.")
        return "Fehler: Die Gemini API ist nicht konfiguriert."

    try:
        model = genai.GenerativeModel(
            GEMINI_MODEL_NAME,
            system_instruction=config.GEMINI_SYSTEM_INSTRUCTION
        )
        
        prompt_parts = []
        
        if context_data:
            prompt_parts.append("\n\n--- BEGINN DES BEREITGESTELLTEN KONTEXTES ---\n")
            prompt_parts.append(context_data)
            prompt_parts.append("\n--- ENDE DES BEREITGESTELLTEN KONTEXTES ---\n")
        
        prompt_parts.append(f"\nBenutzeranfrage: {user_query}")
        
        final_prompt = "\n".join(prompt_parts)

        logging.info(f"Sende Anfrage an Gemini Modell '{GEMINI_MODEL_NAME}'. Länge des Prompts (chars): {len(final_prompt)}")
        if len(final_prompt) > 30000: # Gemini Flash hat ca. 32k Token Limit (Prompt+Antwort)
            logging.warning("Der Prompt ist sehr lang (%s Zeichen), was zu Problemen führen oder die Antwortqualität beeinträchtigen könnte.", len(final_prompt))

        # Konfiguration für die Generierung
        generation_config = types.GenerationConfig(
            temperature=0.6,         # Ein guter Mittelwert für informative Antworten
            max_output_tokens=2000,  # Increased from 1500 to allow longer Discord messages
        )

        # Asynchroner Aufruf
        response = await model.generate_content_async(
            contents=[final_prompt], # 'contents' erwartet eine Liste
            generation_config=generation_config,
        )

        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            generated_text = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text'))
            logging.info(f"Antwort von Gemini erhalten. Länge (chars): {len(generated_text)}")
            return generated_text.strip()
        else:
            block_reason_message = "Unbekannter Blockierungsgrund."
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason_message = f"{response.prompt_feedback.block_reason_message} ({response.prompt_feedback.block_reason})"
                logging.error(f"Gemini-Anfrage blockiert. Grund: {block_reason_message}")
                return f"Meine Antwort wurde leider blockiert. Grund: {response.prompt_feedback.block_reason_message}"
            elif hasattr(response, 'candidates') and response.candidates and response.candidates[0].finish_reason:
                 finish_reason = response.candidates[0].finish_reason
                 logging.warning(f"Keine valide Antwort von Gemini erhalten. Finish Reason: {finish_reason}")
                 if finish_reason == types.Candidate.FinishReason.SAFETY:
                     return "Meine Antwort wurde aufgrund von Sicherheitsrichtlinien blockiert."
                 elif finish_reason == types.Candidate.FinishReason.MAX_TOKENS:
                     return "Die generierte Antwort war zu lang und wurde abgeschnitten."
                 return f"Es tut mir leid, ich konnte keine vollständige Antwort generieren (Grund: {finish_reason})."

            logging.warning(f"Keine valide Antwort oder leerer Inhalt von Gemini erhalten. Full response: {response}")
            return "Es tut mir leid, ich konnte keine Antwort generieren. Die Antwort war leer oder ungültig."

    except types.generation_types.BlockedPromptException as bpe:
        logging.error(f"Gemini-Anfrage wurde aufgrund des Prompts blockiert: {bpe}", exc_info=True)
        return "Ihre Anfrage konnte nicht verarbeitet werden, da sie blockiert wurde. Bitte formulieren Sie Ihre Anfrage um."
    except Exception as e:
        logging.error(f"Fehler bei der Kommunikation mit der Gemini API: {e}", exc_info=True)
        if "API_KEY_INVALID" in str(e) or "API key not valid" in str(e):
            return "Fehler: Der Gemini API Key ist ungültig. Bitte überprüfe die Konfiguration."
        elif "permission" in str(e).lower() or "denied" in str(e).lower():
             return "Fehler: Fehlende Berechtigungen für die Gemini API. Bitte überprüfe die API Key Berechtigungen."
        return f"Ich muss mich kurz ausruhen. Frag mich das nochmal in etwa einer Minute!"

if __name__ == '__main__':
    async def main_test():
        print("\n--- Test des Gemini API Clients (direkt aus gemini_client.py) ---")
        test_query = "Was ist die Kernkompetenz von Safya laut Kontext und wer ist der CTO?"
        test_context = (
            "--- Kontext aus Datei: safya_profil.txt ---\n"
            "Safya ist ein führendes Enterprise AI SaaS-Unternehmen. Unsere Kernkompetenz liegt in der Entwicklung "
            "maßgeschneiderter KI-Lösungen für komplexe Geschäftsprozesse."
            "\n\n---\n\n"
            "--- Kontext aus Datei: team_info.md ---\n"
            "## Unser Team\nCarlos Rodriguez ist der CTO."
        )
        
        if not config.GEMINI_API_KEY or config.GEMINI_API_KEY == "DEIN_GEMINI_API_KEY_HIER":
            print("FEHLER: Kein gültiger Gemini API Key gefunden in .env. Test kann nicht ausgeführt werden.")
            print("Bitte stelle sicher, dass GEMINI_API_KEY in der .env Datei korrekt gesetzt ist.")
            return

        print(f"Anfrage: {test_query}")
        print(f"Mit Kontext (Auszug): {test_context[:100]}...")
        
        response_text = await get_gemini_response(test_query, test_context)
        
        print("\n--- Antwort von Gemini ---")
        print(response_text)
        print("--- Ende der Antwort ---")

    asyncio.run(main_test())
