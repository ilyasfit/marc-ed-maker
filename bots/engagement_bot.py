import discord
from discord.ext import tasks, commands
import datetime
import pytz
import random
import os
import json
from shared import config
from knowledge.engagement_data import POLL_QUESTIONS
from shared import telegram_client # NEU
from shared import config, gemini_client, openai_client
from shared.gemini_client import get_gemini_response # Kept for backward compat in other functions if needed, but we use switch now
from knowledge.vector_store import EmbeddingManager

STATE_FILE_PATH = os.path.join(config.STATE_PATH, 'posted_polls_log.txt')
ACTIVE_POLLS_FILE_PATH = os.path.join(config.STATE_PATH, 'active_polls.json')

class EngagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.posted_indices_cache = self._load_posted_indices()
        self.active_polls_cache = self._load_active_polls()
        self.embedding_manager = EmbeddingManager()
        self.last_run_minute = None  # Verhindert doppelte Ausführungen
        self.master_scheduler.start()

    def _load_posted_indices(self) -> set[int]:
        """Lädt die Indizes der zuletzt geposteten Polls aus der Log-Datei."""
        if not os.path.exists(STATE_FILE_PATH):
            return set()
        try:
            with open(STATE_FILE_PATH, 'r') as f:
                return {int(line.strip()) for line in f if line.strip().isdigit()}
        except Exception as e:
            print(f"FEHLER beim Laden der Poll-Zustandsdatei: {e}")
            return set()

    def _save_posted_index(self, index: int):
        """Speichert den Index eines neuen Polls und rotiert die Liste."""
        self.posted_indices_cache.add(index)
        
        # Behalte nur die letzten 10 Einträge
        all_indices = list(self.posted_indices_cache)
        if len(all_indices) > 10:
            self.posted_indices_cache = set(all_indices[-10:])

        try:
            # Erstelle das Verzeichnis, falls es nicht existiert
            os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
            with open(STATE_FILE_PATH, 'w') as f:
                for idx in self.posted_indices_cache:
                    f.write(f"{idx}\n")
        except Exception as e:
            print(f"FEHLER beim Speichern der Poll-Zustandsdatei: {e}")

    # --- Active Polls State Management (für Poll-Antwort-Reveal) ---
    
    def _load_active_polls(self) -> list[dict]:
        """Lädt aktive Polls aus der JSON-Datei."""
        if not os.path.exists(ACTIVE_POLLS_FILE_PATH):
            return []
        try:
            with open(ACTIVE_POLLS_FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"FEHLER beim Laden der aktiven Polls: {e}")
            return []

    def _save_active_polls(self):
        """Speichert alle aktiven Polls in die JSON-Datei."""
        try:
            os.makedirs(os.path.dirname(ACTIVE_POLLS_FILE_PATH), exist_ok=True)
            with open(ACTIVE_POLLS_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.active_polls_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"FEHLER beim Speichern der aktiven Polls: {e}")

    def _add_active_poll(self, message_id: int, channel_id: int, poll_index: int, poll_data: dict, expires_at: datetime.datetime):
        """Fügt eine neue aktive Poll zum Tracking hinzu."""
        active_poll = {
            "message_id": message_id,
            "channel_id": channel_id,
            "poll_index": poll_index,
            "question": poll_data["question"],
            "answers": poll_data["answers"],
            "expires_at": expires_at.isoformat()
        }
        self.active_polls_cache.append(active_poll)
        self._save_active_polls()
        print(f"INFO: Poll #{poll_index} zum Active-Tracking hinzugefügt. Läuft ab: {expires_at.isoformat()}")

    def _remove_active_poll(self, message_id: int):
        """Entfernt eine Poll aus dem Active-Tracking."""
        self.active_polls_cache = [p for p in self.active_polls_cache if p["message_id"] != message_id]
        self._save_active_polls()
        print(f"INFO: Poll mit Message-ID {message_id} aus Active-Tracking entfernt.")

    async def _generate_poll_answer(self, poll_data: dict) -> str:
        """
        Generiert die korrekte Antwort und eine edukative Erklärung für eine Poll.
        Nutzt den Vector Store für Kontext und LLM für die Antwortgenerierung.
        """
        question = poll_data["question"]
        answers = poll_data["answers"]
        
        # Antwortoptionen formatieren
        options_text = "\n".join([f"{i+1}. {a['text']}" for i, a in enumerate(answers)])
        
        # Vector Store Query für relevanten Kontext
        try:
            query = f"{question} {' '.join([a['text'] for a in answers])}"
            vector_context = await self.bot.loop.run_in_executor(
                None,
                lambda: self.embedding_manager.query_context(query, n_results=5)
            )
        except Exception as e:
            print(f"WARNUNG: Vector Store Query fehlgeschlagen: {e}")
            vector_context = "Kein Kontext verfügbar."

        # System-Prompt für die Antwortgenerierung
        system_prompt = """Du bist Marc Ed Maker, der KI-Experte der Bull VS Bear Academy.
Deine Aufgabe ist es, die korrekte Antwort auf eine Trading-Quiz-Frage zu identifizieren und zu erklären.

Regeln:
- Analysiere die Frage und die Antwortoptionen sorgfältig
- Nutze den bereitgestellten Kontext aus der Knowledge Base
- Identifiziere die EINE korrekte Antwort
- Gib eine kurze, prägnante Erklärung (2-3 Sätze max)
- Schreibe auf Deutsch
- Sei direkt und klar, kein Drumherum

Format deiner Antwort:
**Die richtige Antwort ist: [Antwortnummer]. [Antworttext]**

[Kurze Erklärung warum diese Antwort korrekt ist]"""

        user_prompt = f"""Frage: {question}

Antwortoptionen:
{options_text}

--- KONTEXT AUS DER KNOWLEDGE BASE ---
{vector_context}
--- ENDE KONTEXT ---

Welche Antwort ist korrekt und warum?"""

        # LLM-Antwort generieren
        try:
            if config.LLM_PROVIDER.lower() == 'gemini':
                answer = await gemini_client.get_gemini_response(
                    user_query=user_prompt,
                    context_data="",
                    system_instruction_override=system_prompt
                )
            else:
                if config.OPENAI_API_KEY:
                    answer = await openai_client.get_openai_response(
                        user_query=user_prompt,
                        context_data="",
                        system_instruction_override=system_prompt
                    )
                elif config.GEMINI_API_KEY:
                    answer = await gemini_client.get_gemini_response(
                        user_query=user_prompt,
                        context_data="",
                        system_instruction_override=system_prompt
                    )
                else:
                    return "Fehler: Kein LLM Provider verfügbar."
            
            return answer if answer else "Fehler bei der Antwortgenerierung."
        except Exception as e:
            print(f"FEHLER bei der Antwortgenerierung: {e}")
            return f"Fehler bei der Antwortgenerierung: {e}"

    async def _check_expired_polls(self):
        """
        Prüft alle aktiven Polls auf Ablauf und postet die korrekte Antwort.
        """
        if not self.active_polls_cache:
            return
        
        now = datetime.datetime.now(pytz.UTC)
        expired_polls = []
        
        for poll in self.active_polls_cache:
            expires_at = datetime.datetime.fromisoformat(poll["expires_at"])
            if now >= expires_at:
                # Kopie erstellen, um Race Conditions zu vermeiden
                expired_polls.append(dict(poll))
        
        for poll in expired_polls:
            message_id = poll["message_id"]
            
            # Race-Condition-Check: Ist die Poll noch im Cache?
            if not any(p["message_id"] == message_id for p in self.active_polls_cache):
                print(f"INFO: Poll #{poll['poll_index']} wurde bereits verarbeitet. Überspringe.")
                continue
            
            try:
                print(f"INFO: Poll #{poll['poll_index']} ist abgelaufen. Generiere Antwort...")
                
                # Poll SOFORT aus Cache entfernen, bevor async-Operationen starten
                self._remove_active_poll(message_id)
                
                # Kanal holen
                channel = self.bot.get_channel(poll["channel_id"])
                if not channel:
                    print(f"FEHLER: Kanal {poll['channel_id']} nicht gefunden. Überspringe Poll.")
                    continue
                
                # Antwort generieren
                poll_data = {
                    "question": poll["question"],
                    "answers": poll["answers"]
                }
                answer_text = await self._generate_poll_answer(poll_data)
                
                # Ergebnis-Nachricht formatieren und posten
                result_message = f"""📊 **Die Umfrage ist beendet!**

❓ **Frage:** {poll["question"]}

{answer_text}"""

                await channel.send(result_message)
                print(f"INFO: Antwort für Poll #{poll['poll_index']} erfolgreich gepostet.")
                
            except Exception as e:
                print(f"FEHLER beim Verarbeiten der abgelaufenen Poll #{poll.get('poll_index', '?')}: {e}")

    def _select_poll(self) -> tuple[int, dict] | tuple[None, None]:
        """Wählt einen zufälligen Poll aus, der nicht kürzlich gepostet wurde."""
        all_poll_indices = set(range(len(POLL_QUESTIONS)))
        available_indices = list(all_poll_indices - self.posted_indices_cache)

        if not available_indices:
            # Fallback: Wenn alle Polls kürzlich gepostet wurden, erlaube alle wieder
            print("INFO: Alle Polls wurden kürzlich verwendet. Setze den Cache zurück.")
            self.posted_indices_cache.clear()
            available_indices = list(all_poll_indices)
            if not available_indices: return None, None # Kein Poll verfügbar
        
        chosen_index = random.choice(available_indices)
        return chosen_index, POLL_QUESTIONS[chosen_index]

    async def _execute_poll_posting(self) -> tuple[bool, str]:
        """
        Führt die Logik zum Posten eines Polls aus.
        Returns: (success: bool, message: str)
        """
        channel = self.bot.get_channel(config.POLL_CHANNEL_ID)
        if not channel:
            error = f"Poll-Kanal mit ID {config.POLL_CHANNEL_ID} nicht gefunden."
            print(f"FEHLER: {error}")
            return False, error

        chosen_index, poll_data = self._select_poll()
        if poll_data is None:
            error = "Konnte keinen Poll zum Posten auswählen."
            print(f"FEHLER: {error}")
            return False, error

        try:
            print(f"INFO: Führe Poll-Posting-Task aus für Poll #{chosen_index}.")
            poll_duration = datetime.timedelta(hours=24)
            poll = discord.Poll(
                question=poll_data["question"],
                duration=poll_duration
            )
            for answer in poll_data["answers"]:
                poll.add_answer(text=answer["text"], emoji=answer["emoji"])

            # Message-Objekt capturen für späteres Tracking
            message = await channel.send("@everyone", poll=poll)
            print(f"INFO: Poll #{chosen_index} erfolgreich in Kanal '{channel.name}' gepostet. Message-ID: {message.id}")
            
            # Poll zum Active-Tracking hinzufügen
            expires_at = datetime.datetime.now(pytz.UTC) + poll_duration
            self._add_active_poll(
                message_id=message.id,
                channel_id=channel.id,
                poll_index=chosen_index,
                poll_data=poll_data,
                expires_at=expires_at
            )
            
            self._save_posted_index(chosen_index)
            return True, f"Poll #{chosen_index} gepostet (Message-ID: {message.id})"
        except Exception as e:
            import traceback
            error = f"Fehler beim Senden des Polls: {e}\n{traceback.format_exc()}"
            print(f"FEHLER: {error}")
            return False, str(e)

    async def _execute_telegram_engagement(self, ctx: commands.Context = None):
        """Führt die Logik zum Abrufen und Posten von Telegram-Engagement-Fragen aus."""
        if ctx:
            await ctx.send("Starte die Telegram-Engagement-Aufgabe manuell...")

        print("INFO: Starte Telegram-Engagement-Task.")
        
        # Schritt 1: Nachrichten von Telegram abrufen
        telegram_context = await telegram_client.fetch_recent_messages()
        
        if not telegram_context:
            print("INFO: Telegram-Task wird übersprungen, da kein Kontext gefunden wurde.")
            if ctx:
                await ctx.send("Im Telegram-Kanal wurden keine neuen Inhalte gefunden, um eine Frage zu generieren.")
            return
            
        # Schritt 2: KI-Prompt formulieren
        system_prompt = config.ENGAGEMENT_SYSTEM_PROMPT
        if not system_prompt:
             # Fallback
             system_prompt = (
                "Du bist 'Marc Ed Maker', der KI-Assistent von Bull VS Bear Academy. Deine Aufgabe ist es, die folgende Sammlung von Nachrichten und Diskussionen "
                "aus einem Krypto-Nachrichtenkanal zu analysieren. Dein Ziel ist es, diese Informationen in eine einzige, kurze und "
                "ansprechende Frage für die Bull VS Bear Academy zu destillieren. Die Frage sollte auf Deutsch sein, "
                "natürlich und organisch klingen und zu Debatten und Diskussionen anregen. Fasse die Nachrichten nicht zusammen, sondern stelle nur eine "
                "intelligente Frage zum relevantesten Thema, das du findest. Beispiel: 'Leute, was glaubt ihr, wie sich die jüngsten Nachrichten über X "
                "auf Y auswirken werden? Bin gespannt auf eure Meinung.' Sei direkt und prägnant."
            )
        
        if ctx:
            await ctx.send("Generiere Frage mit der KI...")

        user_query = "Formuliere eine ansprechende Frage basierend auf dem bereitgestellten Kontext."
        
        question = ""
        if config.LLM_PROVIDER.lower() == 'gemini':
            question = await gemini_client.get_gemini_response(
                user_query=user_query,
                context_data=telegram_context,
                system_instruction_override=system_prompt
            )
        else:
             # Default to OpenAI
            if config.OPENAI_API_KEY:
                question = await openai_client.get_openai_response(
                    user_query=user_query,
                    context_data=telegram_context,
                    system_instruction_override=system_prompt
                )
            elif config.GEMINI_API_KEY:
                print("WARNUNG: OpenAI konfiguriert aber kein Key. Fallback auf Gemini.")
                question = await gemini_client.get_gemini_response(
                    user_query=user_query,
                    context_data=telegram_context,
                    system_instruction_override=system_prompt
                )
            else:
                 print("FEHLER: Kein LLM Provider verfügbar.")
        
        if not question or "konnte nicht" in question.lower() or "nicht in der Lage" in question.lower():
            print("FEHLER: Gemini konnte keine gültige Frage generieren.")
            if ctx:
                await ctx.send("Die KI konnte aus dem Inhalt keine gültige Frage generieren.")
            return

        # Schritt 3: Frage im Discord-Kanal posten
        channel = self.bot.get_channel(config.TELEGRAM_POST_CHANNEL_ID)
        if not channel:
            error_msg = f"FEHLER: Telegram-Post-Kanal mit ID {config.TELEGRAM_POST_CHANNEL_ID} nicht gefunden."
            print(error_msg)
            if ctx:
                await ctx.send(error_msg)
            return
            
        try:
            await channel.send(question)
            success_msg = f"INFO: Telegram-Engagement-Post erfolgreich in Kanal '{channel.name}' gesendet."
            print(success_msg)
            if ctx:
                await ctx.send(f"Frage erfolgreich an den Kanal {channel.mention} gesendet!")
        except Exception as e:
            error_msg = f"FEHLER beim Senden der Telegram-Engagement-Frage: {e}"
            print(error_msg)
            if ctx:
                await ctx.send(error_msg)

    @tasks.loop(seconds=60)
    async def master_scheduler(self):
        """
        Ein zentraler Scheduler, der jede Minute läuft und prüft, ob geplante Tasks ausgeführt werden müssen.
        """
        await self.bot.wait_until_ready()
        
        # --- Abgelaufene Polls prüfen (läuft bei jedem Loop) ---
        await self._check_expired_polls()
        
        now_utc = datetime.datetime.now(pytz.UTC)
        current_minute_str = now_utc.strftime('%Y-%m-%d %H:%M')

        # Verhindert doppelte Ausführung, falls der Bot innerhalb derselben Minute neu startet
        if self.last_run_minute == current_minute_str:
            return
        
        current_weekday = now_utc.weekday()
        current_time_str = now_utc.strftime('%H:%M')
        
        task_has_run = False

        # --- Poll Task 1 Check ---
        if current_weekday == config.POLL_SCHEDULE_1_DAY and current_time_str == config.POLL_SCHEDULE_1_TIME:
            print(f"SCHEDULER: Zeit für Poll 1 erreicht. Führe Task aus.")
            await self._execute_poll_posting()
            task_has_run = True

        # --- Poll Task 2 Check ---
        if current_weekday == config.POLL_SCHEDULE_2_DAY and current_time_str == config.POLL_SCHEDULE_2_TIME:
            print(f"SCHEDULER: Zeit für Poll 2 erreicht. Führe Task aus.")
            await self._execute_poll_posting()
            task_has_run = True

        # --- Telegram Task Check ---
        if current_weekday == config.TELEGRAM_SCHEDULE_DAY and current_time_str == config.TELEGRAM_SCHEDULE_TIME:
            print(f"SCHEDULER: Zeit für Telegram-Task erreicht. Führe Task aus.")
            await self._execute_telegram_engagement()
            task_has_run = True
            
        if task_has_run:
            self.last_run_minute = current_minute_str

    @commands.command()
    @commands.is_owner()
    async def post_poll(self, ctx):
        """Posts a poll manually for testing."""
        await ctx.send("Erzwinge das Senden einer Umfrage...")
        
        # Debug: Zeige konfigurierte Channel-ID
        if not config.POLL_CHANNEL_ID:
            await ctx.send("❌ **FEHLER:** `POLL_CHANNEL_ID` ist nicht in `.env` konfiguriert!")
            return
        
        channel = self.bot.get_channel(config.POLL_CHANNEL_ID)
        if not channel:
            await ctx.send(f"❌ **FEHLER:** Kanal mit ID `{config.POLL_CHANNEL_ID}` nicht gefunden!")
            return
        
        await ctx.send(f"📍 Ziel-Kanal: {channel.mention}")
        
        success, message = await self._execute_poll_posting()
        
        if success:
            await ctx.send(f"✅ **Erfolg:** {message}\nPrüfe mit `!list_active_polls`")
        else:
            await ctx.send(f"❌ **FEHLER beim Poll-Posting:**\n```\n{message[:1500]}\n```")

    @commands.command()
    @commands.is_owner()
    async def post_telegram_q(self, ctx):
        """Triggers the Telegram engagement task manually."""
        await self._execute_telegram_engagement(ctx)

    @commands.command()
    @commands.is_owner()
    async def test_poll_reveal(self, ctx, poll_index: int = 0):
        """
        Testet die Poll-Antwort-Generierung ohne eine echte Poll zu posten.
        Usage: !test_poll_reveal [poll_index]
        """
        if poll_index < 0 or poll_index >= len(POLL_QUESTIONS):
            await ctx.send(f"Ungültiger Poll-Index. Verfügbar: 0-{len(POLL_QUESTIONS)-1}")
            return
        
        poll_data = POLL_QUESTIONS[poll_index]
        await ctx.send(f"Teste Poll-Antwort-Generierung für Poll #{poll_index}...\n\n**Frage:** {poll_data['question']}")
        
        try:
            answer = await self._generate_poll_answer(poll_data)
            result_message = f"""📊 **Test: Poll-Antwort-Reveal**

❓ **Frage:** {poll_data["question"]}

{answer}"""
            await ctx.send(result_message)
        except Exception as e:
            await ctx.send(f"Fehler bei der Antwortgenerierung: {e}")

    @commands.command()
    @commands.is_owner()
    async def list_active_polls(self, ctx):
        """Zeigt alle aktiven (noch nicht abgelaufenen) Polls an."""
        if not self.active_polls_cache:
            await ctx.send("Keine aktiven Polls im Tracking.")
            return
        
        now = datetime.datetime.now(pytz.UTC)
        message = "**Aktive Polls im Tracking:**\n\n"
        
        for poll in self.active_polls_cache:
            expires_at = datetime.datetime.fromisoformat(poll["expires_at"])
            remaining = expires_at - now
            status = "⏳ Läuft" if remaining.total_seconds() > 0 else "✅ Abgelaufen"
            
            message += f"• Poll #{poll['poll_index']}: {poll['question'][:50]}...\n"
            message += f"  Message-ID: {poll['message_id']} | {status}\n"
            message += f"  Läuft ab: {expires_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        
        await ctx.send(message[:2000])  # Discord message limit

    @commands.command()
    @commands.is_owner()
    async def force_poll_reveal(self, ctx, message_id: int = None):
        """
        Erzwingt die sofortige Antwort-Enthüllung für eine aktive Poll.
        Usage: !force_poll_reveal [message_id]
        Ohne message_id wird die älteste aktive Poll aufgelöst.
        """
        if not self.active_polls_cache:
            await ctx.send("Keine aktiven Polls im Tracking.")
            return
        
        if message_id:
            poll = next((p for p in self.active_polls_cache if p["message_id"] == message_id), None)
            if not poll:
                await ctx.send(f"Keine aktive Poll mit Message-ID {message_id} gefunden.")
                return
        else:
            poll = self.active_polls_cache[0]
        
        await ctx.send(f"Erzwinge Antwort-Reveal für Poll #{poll['poll_index']}...")
        
        # Expiry auf jetzt setzen, damit der nächste Scheduler-Durchlauf sie aufgreift
        poll["expires_at"] = datetime.datetime.now(pytz.UTC).isoformat()
        self._save_active_polls()
        
        # Direkt auslösen
        await self._check_expired_polls()
        await ctx.send("Poll-Reveal ausgelöst!")

    @commands.command()
    @commands.is_owner()
    async def post_poll_short(self, ctx, minutes: int = 2):
        """
        Postet eine Poll und setzt das Tracking-Expiry auf wenige Minuten für QA-Tests.
        Die Discord-Poll läuft normal 1h, aber unser Bot denkt sie läuft nur X Minuten.
        Usage: !post_poll_short [minutes]
        Default: 2 Minuten
        """
        if minutes < 1 or minutes > 60:
            await ctx.send("Minuten müssen zwischen 1 und 60 liegen.")
            return
        
        channel = self.bot.get_channel(config.POLL_CHANNEL_ID)
        if not channel:
            await ctx.send(f"❌ **FEHLER:** Kanal mit ID `{config.POLL_CHANNEL_ID}` nicht gefunden!")
            return
        
        chosen_index, poll_data = self._select_poll()
        if poll_data is None:
            await ctx.send("❌ Konnte keinen Poll auswählen.")
            return
        
        await ctx.send(f"📍 Poste QA-Test-Poll in: {channel.mention}\n⏱️ Tracking-Expiry: {minutes} Min (Discord-Poll läuft 1h)")
        
        try:
            # Discord-Poll muss mindestens 1 Stunde laufen
            poll = discord.Poll(
                question=f"[QA-TEST] {poll_data['question']}",
                duration=datetime.timedelta(hours=1)
            )
            for answer in poll_data["answers"]:
                poll.add_answer(text=answer["text"], emoji=answer["emoji"])
            
            message = await channel.send("@everyone", poll=poll)
            
            # Aber unser Tracking läuft nur X Minuten
            expires_at = datetime.datetime.now(pytz.UTC) + datetime.timedelta(minutes=minutes)
            self._add_active_poll(
                message_id=message.id,
                channel_id=channel.id,
                poll_index=chosen_index,
                poll_data=poll_data,
                expires_at=expires_at
            )
            
            self._save_posted_index(chosen_index)
            await ctx.send(f"✅ **QA-Test-Poll gepostet!**\n• Poll #{chosen_index}\n• Message-ID: {message.id}\n• Antwort-Reveal in: **{minutes} Min** ({expires_at.strftime('%H:%M:%S UTC')})\n• Der Scheduler prüft alle 60s - Antwort kommt automatisch!")
        except Exception as e:
            import traceback
            await ctx.send(f"❌ **FEHLER:** {e}\n```{traceback.format_exc()[:500]}```")

# Setup-Funktion, die von run.py aufgerufen wird
async def setup_engagement(bot):
    await bot.add_cog(EngagementCog(bot))
    print("Engagement-Engine-Modul (Polls) erfolgreich geladen.")
