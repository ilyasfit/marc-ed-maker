"""
knowledge/macro_data.py

Bias-Regeln und relevante Keywords für das Macro-Briefing.
Die Regeln sind bewusst datengetrieben gehalten, sodass sie später
einfach erweitert oder durch ein externes Management-Interface ersetzt werden können.
"""

# --- Überarbeitete Bias-Regeln und Keywords (Variante C: positiv/negativ explizit) ---
BIAS_RULES = {
    # --- INFLATION ---
    "CPI": {
        "template": "🔴 {time} – {title} (Erwartung {forecast}). ✅ Positiv für Krypto, wenn niedriger als erwartet; ❌ negativ, wenn höher als erwartet."
    },
    "CORE CPI": {
        "template": "🔴 {time} – {title} (Erwartung {forecast}). Core zählt stärker: ✅ niedriger = positiv; ❌ höher = negativ."
    },
    "PPI": {
        "template": "🟠 {time} – {title} (Erwartung {forecast}). ✅ niedriger als erwartet = positiv; ❌ höher = negativ."
    },
    "PCE": {
        "template": "🔴 {time} – {title} (Erwartung {forecast}). (Fed-präferiert) ✅ niedriger = positiv; ❌ höher = negativ."
    },
    "CORE PCE": {
        "template": "🔴 {time} – {title} (Erwartung {forecast}). ✅ unter Erwartung = positiv; ❌ darüber = negativ."
    },
    "VERBRAUCHERPREISINDEX": {
        "template": "🔴 {time} – {title} (Erwartung {forecast}). ✅ niedriger = positiv; ❌ höher = negativ."
    },

    # --- ZINS / ZENTRALBANK ---
    "FED INTEREST RATE DECISION": {
        "template": "🟠 {time} – {title} (Erwartung {forecast}). ✅ positiv bei Pause/Cut ggü. Erwartung oder dovishem Ton; ❌ negativ bei Anhebung über Erwartung oder hawkisher Guidance."
    },
    "FOMC": {
        "template": "🟠 {time} – {title}. ✅ dovisher als erwartet = positiv; ❌ hawkisher als erwartet = negativ."
    },
    "ECB INTEREST RATE DECISION": {
        "template": "🟠 {time} – {title} (Erwartung {forecast}). ✅ positiv bei Pause/Cut ggü. Erwartung; ❌ negativ bei hawkisher Überraschung."
    },
    "ZINSENTSCHEIDUNG": {
        "template": "🟠 {time} – {title} (Erwartung {forecast}). ✅ Pause/Cut vs. Erwartung = positiv; ❌ straffer als erwartet = negativ."
    },

    # --- ARBEITSMARKT ---
    "NON-FARM PAYROLLS": {
        "template": "🟠 {time} – {title} (Erwartung {forecast}). ❌ deutlich stärker = hawkish Risiko; ❌ deutlich schwächer = Rezessionsangst; ✅ leicht unter Erwartung kann positiv wirken."
    },
    "UNEMPLOYMENT RATE": {
        "template": "🟠 {time} – {title} (Erwartung {forecast}). ❌ niedriger als erwartet = hawkish Risiko; ❌ viel höher = Rezessionssorgen; ✅ marginal höher kann dovish interpretiert werden."
    },
    "AVERAGE HOURLY EARNINGS": {
        "template": "🟠 {time} – {title} (Erwartung {forecast}). ❌ über Erwartung (inflationär); ✅ darunter (disinflationär)."
    },
    "INITIAL JOBLESS CLAIMS": {
        "template": "🟠 {time} – {title} (Erwartung {forecast}). ❌ weniger Anträge = hawkish Risiko; ❌ deutlich mehr = risk-off; ✅ moderat höher = etwas dovisher."
    },

    # --- WACHSTUM / NACHFRAGE ---
    "GDP": {
        "template": "🟠 {time} – {title} (Erwartung {forecast}). ❌ deutlich stärker = hawkish Risiko; ❌ deutlich schwächer = Rezessionsangst; ✅ leicht schwächer kann dovish sein."
    },
    "RETAIL SALES": {
        "template": "🟠 {time} – {title} (Erwartung {forecast}). ❌ viel stärker = hawkish; ❌ viel schwächer = risk-off; ✅ leicht darunter = dovish."
    },

    # --- STIMMUNG / AKTIVITÄT ---
    "PMI": {
        "template": "🟠 {time} – {title} (Erwartung {forecast}). ❌ starke Überschreitung = hawkish; ❌ starke Unterschreitung = Wachstumssorge; ✅ leichte Unterschreitung kann positiv sein."
    },
    "ISM": {
        "template": "🟠 {time} – {title} (Erwartung {forecast}). ❌ weit über Erwartung = hawkish; ❌ weit darunter = risk-off; ✅ moderat darunter = dovish."
    }
}

RELEVANT_EVENT_KEYWORDS = [
    # Inflation
    "CPI", "CORE CPI", "PPI", "PCE", "CORE PCE", "VERBRAUCHERPREISINDEX",
    # Rates / CB
    "FED INTEREST RATE DECISION", "FOMC", "ECB INTEREST RATE DECISION", "ZINSENTSCHEIDUNG",
    # Labor
    "NON-FARM PAYROLLS", "UNEMPLOYMENT RATE", "AVERAGE HOURLY EARNINGS", "INITIAL JOBLESS CLAIMS",
    # Growth / Demand
    "GDP", "RETAIL SALES",
    # Sentiment/Activity
    "PMI", "ISM"
]
