import discord
from discord.ext import tasks, commands
import datetime
import pytz
import aiohttp
import asyncio
from shared import config
from shared.gemini_client import get_gemini_response
from knowledge.macro_data import BIAS_RULES, RELEVANT_EVENT_KEYWORDS

TIMEZONE = pytz.timezone('Europe/Berlin')

STATE_DUMMY = None  # Platzhalter für möglichen zukünftigen Zustandsspeicher

class MacroBriefCog(commands.Cog):
    """
    Cog, das einmal täglich (konfigurierbar) ein kurzes Makro-Briefing in einen Kanal postet.
    Implementiert einen Master-Scheduler (wie in engagement_bot.py), der jede Minute läuft
    und prüft, ob die konfigurierte Zeit erreicht ist.
    """

    def __init__(self, bot):
        self.bot = bot
        self.last_run_minute = None
        self.master_scheduler.start()

    async def cog_unload(self):
        self.master_scheduler.cancel()

    async def _fetch_calendar_data(self):
        """
        Versucht zuerst, die CRYPTO_CRAFT_URL zu laden, und fällt auf FOREX_FACTORY_URL zurück.
        Erwartet JSON-Array oder -Objekt mit Events.
        """
        urls = [config.CRYPTO_CRAFT_URL, config.FOREX_FACTORY_URL]
        async with aiohttp.ClientSession() as session:
            for url in urls:
                if not url:
                    continue
                try:
                    async with session.get(url, timeout=15) as resp:
                        if resp.status == 200:
                            try:
                                return await resp.json()
                            except Exception as e:
                                print(f"FEHLER: JSON-Parsing für {url} fehlgeschlagen: {e}")
                        else:
                            print(f"WARNUNG: {url} antwortete mit Status {resp.status}")
                except Exception as e:
                    print(f"WARNUNG: Fehler beim Abrufen von {url}: {e}")
        return None

    def _parse_event_datetime(self, event):
        """
        Robustere Datum/Time-Parsing-Logik.
        Erwartet Felder wie 'date', 'time', 'datetime' (ISO8601). Gibt ein timezone-aware datetime zurück oder None.
        """
        candidates = []
        for key in ('datetime', 'date', 'time', 'date_utc', 'utc'):
            v = event.get(key) if isinstance(event, dict) else None
            if v:
                candidates.append(v)

        for raw in candidates:
            try:
                # normalize 'Z' suffix
                s = raw.replace('Z', '+00:00') if isinstance(raw, str) else None
                if not s:
                    continue
                dt = datetime.datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    # assume UTC if naive
                    dt = dt.replace(tzinfo=pytz.UTC)
                return dt.astimezone(TIMEZONE)
            except Exception:
                continue
        return None

    def _filter_events_for_today(self, all_events):
        """
        Filtert Events für das heutige Datum in Europe/Berlin und solche mit relevantem Impact/Keyword.
        Erwartet eine Liste von Event-Objekten.
        """
        if not all_events:
            return []

        now = datetime.datetime.now(TIMEZONE)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + datetime.timedelta(days=1)

        today_events = []
        # If the JSON is a dict with a key for events, try to extract common shapes
        if isinstance(all_events, dict):
            # common shapes: {'events': [...]} or calendar like structures
            for possible in ('events', 'data', 'calendar', 'items'):
                if possible in all_events and isinstance(all_events[possible], list):
                    all_events = all_events[possible]
                    break
            else:
                # If dict but not containing lists, try to treat values as list
                extracted = []
                for v in all_events.values():
                    if isinstance(v, list):
                        extracted.extend(v)
                if extracted:
                    all_events = extracted

        if not isinstance(all_events, list):
            return []

        for event in all_events:
            try:
                event_dt = self._parse_event_datetime(event)
                if not event_dt:
                    continue

                is_today = (start_of_day <= event_dt < end_of_day)
                impact = (event.get('impact') or '').lower()
                title = event.get('title') or event.get('event') or ''

                is_relevant_impact = impact in ['high', 'medium']
                # keyword match case-insensitive
                title_upper = title.upper()
                is_relevant_keyword = any(k.upper() in title_upper for k in RELEVANT_EVENT_KEYWORDS)

                if is_today and (is_relevant_impact or is_relevant_keyword):
                    # attach parsed datetime for later formatting
                    event['_parsed_dt'] = event_dt
                    today_events.append(event)
            except Exception as e:
                print(f"WARNUNG: Fehler beim Verarbeiten eines Events: {e}")
                continue

        # sort by parsed datetime
        return sorted(today_events, key=lambda x: x.get('_parsed_dt') or datetime.datetime.max.replace(tzinfo=TIMEZONE))

    def _format_briefing(self, events):
        now = datetime.datetime.now(TIMEZONE)
        header = f"📅 **Daily Macro Brief – {now.strftime('%d.%m.%Y')}**\n"

        if not events:
            return header + "\nHeute stehen keine wichtigen, Krypto-relevanten Makro-Events an. Ein ruhiger Tag an der Makro-Front!"

        lines = []
        for event in events:
            title = event.get('title') or event.get('event') or 'Unbenanntes Event'
            dt = event.get('_parsed_dt') or self._parse_event_datetime(event) or now
            time_str = dt.strftime('%H:%M %Z')
            forecast = (
                event.get('forecast') or event.get('estimate') or
                event.get('consensus') or event.get('expected') or
                event.get('expected_value') or 'N/A'
            )

            # apply bias rule lookup (case-insensitive contains)
            matched = False
            for keyword, rule in BIAS_RULES.items():
                if keyword.upper() in title.upper():
                    try:
                        line = rule['template'].format(time=time_str, title=title, forecast=forecast)
                    except Exception:
                        line = f"🟠 {time_str} – {title} (Erwartung {forecast})."
                    lines.append(line)
                    matched = True
                    break

            if not matched:
                # generic fallback for relevant events
                lines.append(f"🟠 {time_str} – {title} (Erwartung {forecast}).")

        return header + "\n".join(lines)

    @tasks.loop(seconds=60)
    async def master_scheduler(self):
        """
        Läuft jede Minute und prüft, ob die konfigurierte Uhrzeit erreicht ist.
        Verhält sich analog zum Scheduler in engagement_bot.py.
        """
        await self.bot.wait_until_ready()
        now_utc = datetime.datetime.now(pytz.UTC)
        current_minute_str = now_utc.strftime('%Y-%m-%d %H:%M')

        # Verhindert doppelte Ausführung in derselben Minute
        if self.last_run_minute == current_minute_str:
            return

        now_local = datetime.datetime.now(TIMEZONE)
        current_weekday = now_local.weekday()  # 0=Mo .. 6=So
        current_time_str = now_local.strftime('%H:%M')

        # Only weekdays
        if current_weekday >= 5:
            return

        # configured time may include quotes in .env; strip them
        configured_time = config.MACRO_BRIEF_SCHEDULE_TIME.strip().strip('"').strip("'")
        if current_time_str == configured_time:
            # run the task
            print("INFO: Führe Macro-Briefing Task aus.")
            await self._run_briefing_task()

            self.last_run_minute = current_minute_str

    async def _run_briefing_task(self, ctx: commands.Context = None):
        """
        Fetch, filter, format, and post the macro briefing.
        If ctx is provided, send feedback to ctx.
        """
        if ctx:
            await ctx.send("Starte das Makro-Briefing...")

        events_raw = await self._fetch_calendar_data()
        if not events_raw:
            msg = "FEHLER: Konnte keine Kalenderdaten abrufen. Überspringe das Briefing."
            print(msg)
            if ctx:
                await ctx.send(msg)
            return

        today_events = self._filter_events_for_today(events_raw)

        # Versuche, ein kompaktes, narratives Briefing mittels Gemini zu erzeugen.
        # Wir bauen einen kurzen, strukturierten Kontext (eine Zeile pro Event) und
        # senden diesen zusammen mit einer klaren System-Instruktion an das LLM.
        try:
            now = datetime.datetime.now(TIMEZONE)

            # Strukturierte Event-Items vorbereiten
            items = []
            for ev in today_events:
                ev_dt = ev.get('_parsed_dt') or self._parse_event_datetime(ev) or now
                t = ev_dt.strftime('%H:%M %Z')
                title = (ev.get('title') or ev.get('event') or '').replace('\n', ' ').strip()
                forecast = (
                    ev.get('forecast') or ev.get('estimate') or
                    ev.get('consensus') or ev.get('expected') or
                    ev.get('expected_value') or 'N/A'
                )
                impact = (ev.get('impact') or '').lower()
                matched_kw = None
                for kw in RELEVANT_EVENT_KEYWORDS:
                    if kw.upper() in title.upper():
                        matched_kw = kw
                        break
                items.append({
                    "time": t,
                    "title": title,
                    "forecast": forecast,
                    "impact": impact,
                    "keyword": matched_kw
                })

            if not items:
                message = self._format_briefing(today_events)
            else:
                # Priorisierung: High -> Medium -> Others
                high = [it for it in items if it["impact"] == "high"]
                medium = [it for it in items if it["impact"] == "medium"]
                candidates = high or medium or items
                top = candidates[:2]
                secondary = [it for it in items if it not in top][:2]

                # Gruppiere Inflations-Items zu einem Block, falls mehrere vorhanden
                inflation_keys = {"CPI", "CORE CPI", "PCE", "CORE PCE", "MEDIAN", "TRIMMED", "VERBRAUCHERPREISINDEX"}
                inflation_items = [it for it in items if it["keyword"] and any(k in it["keyword"].upper() for k in inflation_keys)]
                grouped_lines = []
                if len(inflation_items) > 1:
                    times = ", ".join(sorted({it["time"] for it in inflation_items}))
                    forecasts = ", ".join(sorted({it["forecast"] for it in inflation_items if it["forecast"] != "N/A"})) or "N/A"
                    grouped_lines.append(f"{times} | INFLATIONSDATEN (CPI/Core/Median/Trimmed) | Erwartung: {forecasts}")
                    # Entferne diese aus Top/Secondary, falls sie dort waren
                    top = [it for it in top if it not in inflation_items]
                    secondary = [it for it in secondary if it not in inflation_items]

                # Kompakte Kontextzeilen: Top, Gruppiert, Secondary
                context_lines = []
                for it in top:
                    context_lines.append(f'{it["time"]} | {it["keyword"] or "GENERAL"} | {it["title"]} | {it["forecast"]} | impact={it["impact"]}')
                context_lines.extend(grouped_lines)
                for it in secondary:
                    context_lines.append(f'{it["time"]} | {it["keyword"] or "GENERAL"} | {it["title"]} | {it["forecast"]} | impact={it["impact"]}')

                compact_context = "\n".join(context_lines) if context_lines else "keine Events"

                system_instruction = """Du bist ein professioneller, prägnanter Macro-Briefer für Krypto-Trader.
Formuliere aus dem bereitgestellten Kontext ein kurzes, lesbares Briefing auf Deutsch (maximal 6 Zeilen):
- 1–2 Top-Prioritäten (🔴) mit sehr kurzer Begründung (Warum relevant für Krypto?)
- 1–2 sekundäre Events (🟠) kurz genannt
- 1 kurzer Fazit-Satz (Was bedeutet das heute für BTC/ETH?)
- Bias-Schluss (🐂/🐻/💤) am Ende

Beispielausgabe:
🔴 14:30 CEST – US Inflationsdaten (CPI/Core): Erwartung ~3.0–3.2%. Kurz: Höher = Druck auf Risikoassets, Niedriger = Erleichterung.
🟠 16:00 CEST – Retail Sales: Erwartung 0.2–0.4%.
📌 Fazit: Fokus auf Inflationsdaten. Überraschung nach oben = Risiko für BTC.
Bias: 🐻

Wichtig: Halte Sprache einfach, vermeide viele 'wenn/dann' Klauseln. Nutze Zeiten im Format '14:30 CEST'."""

                ai_text = await get_gemini_response(
                    user_query="Formuliere ein kurzes Daily Macro Briefing basierend auf dem Kontext.",
                    context_data=compact_context,
                    system_instruction_override=system_instruction
                )

                if ai_text and isinstance(ai_text, str) and ai_text.strip():
                    message = f"📅 **Daily Macro Brief – {now.strftime('%d.%m.%Y')}**\n\n{ai_text.strip()}"
                else:
                    message = self._format_briefing(today_events)
        except Exception as e:
            print(f"WARNUNG: Gemini-Formatting fehlgeschlagen: {e}")
            message = self._format_briefing(today_events)

        channel = self.bot.get_channel(config.MACRO_BRIEF_CHANNEL_ID)
        if not channel:
            err = f"FEHLER: Makro-Briefing-Kanal mit ID {config.MACRO_BRIEF_CHANNEL_ID} nicht gefunden."
            print(err)
            if ctx:
                await ctx.send(err)
            return

        try:
            await channel.send(message)
            info = f"INFO: Makro-Briefing erfolgreich an Kanal '{channel.name}' gesendet."
            print(info)
            if ctx:
                await ctx.send("Makro-Briefing gesendet.")
        except Exception as e:
            err = f"FEHLER beim Senden des Makro-Briefings: {e}"
            print(err)
            if ctx:
                await ctx.send(err)

    @commands.command()
    @commands.is_owner()
    async def post_macro_brief(self, ctx):
        """Manuell ein Makro-Briefing auslösen (nur Bot-Owner)."""
        await ctx.send("Erzwinge das Senden des Makro-Briefings...")
        await self._run_briefing_task(ctx)

# Setup-Funktion, die von run.py aufgerufen wird
async def setup_macro_brief(bot):
    await bot.add_cog(MacroBriefCog(bot))
    print("Macro-briefing Modul erfolgreich geladen.")
