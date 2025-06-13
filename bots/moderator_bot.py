import discord
from shared import config
from .moderator_filters import load_list_from_file, contains_forbidden_link, find_forbidden_content
import os

async def setup_moderator(bot):
    # Lade Wissensdatenbanken über den zentralen Config-Pfad
    whitelisted_domains = load_list_from_file(os.path.join(config.MODERATOR_RULES_PATH, 'whitelisted_domains.txt'))
    forbidden_words = load_list_from_file(os.path.join(config.MODERATOR_RULES_PATH, 'forbidden_words.txt'))
    seedphrase_patterns = load_list_from_file(os.path.join(config.MODERATOR_RULES_PATH, 'seedphrases.txt'))

    hugo_user = await bot.fetch_user(config.HUGO_DISCORD_ID)

    async def moderator_check(message: discord.Message):
        # Ignoriere Nachrichten vom Bot selbst oder aus DMs (obwohl dies in run.py bereits geschieht)
        if message.author == bot.user or message.guild is None:
            return False

        # Prüfe, ob eine Moderationsaktion notwendig ist
        moderation_reason = None
        if contains_forbidden_link(message.content, whitelisted_domains):
            moderation_reason = "Partilha de links não autorizados"
        else:
            moderation_reason = find_forbidden_content(message.content, forbidden_words, seedphrase_patterns)

        if moderation_reason:
            await trigger_moderation_action(message, moderation_reason, hugo_user)
            return True # Nachricht wurde behandelt

        return False # Keine Aktion durchgeführt

    print("Moderator-Modul erfolgreich geladen.")
    return moderator_check

async def trigger_moderation_action(message, reason: str, hugo_user: discord.User):
    """Führt die standardisierte Moderationsaktion aus."""
    # ... (Diese Funktion kann fast 1:1 aus der alten moderator/bot.py übernommen werden)
    author = message.author
    
    try:
        await message.delete()
    except discord.errors.Forbidden:
        print(f"FEHLER: Keine Berechtigung, die Nachricht von {author.name} zu löschen.")
        return
    except discord.errors.NotFound:
        pass

    dm_text_user = (
        f"Atenção, a tua mensagem recente no servidor BitVision violou as nossas diretrizes da comunidade ({reason}). "
        "Por favor, revê as nossas regras para garantir eine boa convivência. "
        "Violações repetidas poderão resultar em silenciamento temporário ou banimento."
    )
    try:
        await author.send(dm_text_user)
    except discord.errors.Forbidden:
        print(f"WARNUNG: Konnte keine DM an {author.name} senden.")

    if hugo_user:
        alert_text_hugo = (
            f"**Alerta de Moderação (Imperius Vox)**\n\n"
            f"**Utilizador:** {author.name} (`{author.id}`)\n"
            f"**Ação:** Mensagem eliminada\n"
            f"**Motivo:** {reason}\n"
            f"**Conteúdo da Mensagem:**\n> {message.content}"
        )
        try:
            await hugo_user.send(alert_text_hugo)
        except discord.errors.Forbidden:
            print(f"FEHLER: Konnte keine DM an Hugo senden.")
    
    print(f"Aktion durchgeführt: Nachricht von {author.name} wegen '{reason}' gelöscht.")
