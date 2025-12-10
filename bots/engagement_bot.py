import discord
from discord.ext import tasks, commands
import datetime
import pytz
import random
import os
from shared import config
from knowledge.engagement_data import POLL_QUESTIONS
from shared import telegram_client # NEU
from shared.gemini_client import get_gemini_response # NEU

STATE_FILE_PATH = os.path.join(config.STATE_PATH, 'posted_polls_log.txt')

class EngagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.posted_indices_cache = self._load_posted_indices()
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

    async def _execute_poll_posting(self):
        """Führt die Logik zum Posten eines Polls aus."""
        channel = self.bot.get_channel(config.POLL_CHANNEL_ID)
        if not channel:
            print(f"FEHLER: Poll-Kanal mit ID {config.POLL_CHANNEL_ID} nicht gefunden.")
            return

        chosen_index, poll_data = self._select_poll()
        if poll_data is None:
            print("FEHLER: Konnte keinen Poll zum Posten auswählen.")
            return

        try:
            print(f"INFO: Führe Poll-Posting-Task aus für Poll #{chosen_index}.")
            poll = discord.Poll(
                question=poll_data["question"],
                duration=datetime.timedelta(hours=24)
            )
            for answer in poll_data["answers"]:
                poll.add_answer(text=answer["text"], emoji=answer["emoji"])

            await channel.send("@everyone", poll=poll)
            print(f"INFO: Poll #{chosen_index} erfolgreich in Kanal '{channel.name}' gepostet.")
            self._save_posted_index(chosen_index)
        except Exception as e:
            print(f"FEHLER beim Senden des Polls: {e}")

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

        question = await get_gemini_response(
            user_query="Formuliere eine ansprechende Frage basierend auf dem bereitgestellten Kontext.",
            context_data=telegram_context,
            system_instruction_override=system_prompt
        )
        
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
        await self._execute_poll_posting()

    @commands.command()
    @commands.is_owner()
    async def post_telegram_q(self, ctx):
        """Triggers the Telegram engagement task manually."""
        await self._execute_telegram_engagement(ctx)

# Setup-Funktion, die von run.py aufgerufen wird
async def setup_engagement(bot):
    await bot.add_cog(EngagementCog(bot))
    print("Engagement-Engine-Modul (Polls) erfolgreich geladen.")
