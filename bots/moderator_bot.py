import discord
from discord.ext import commands
from shared import config
from .moderator_filters import load_list_from_file, contains_forbidden_link, find_forbidden_content
import os

class ModeratorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.whitelisted_domains = load_list_from_file(os.path.join(config.MODERATOR_RULES_PATH, 'whitelisted_domains.txt'))
        self.forbidden_words = load_list_from_file(os.path.join(config.MODERATOR_RULES_PATH, 'forbidden_words.txt'))
        self.forbidden_memecoins = load_list_from_file(os.path.join(config.MODERATOR_RULES_PATH, 'memecoins.txt'))
        self.seedphrase_patterns = load_list_from_file(os.path.join(config.MODERATOR_RULES_PATH, 'seedphrases.txt'))
        self.hugo_user = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.hugo_user = await self.bot.fetch_user(config.HUGO_DISCORD_ID)
        print("Moderator-Modul bereit.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user or message.guild is None:
            return

        moderation_reason = None
        # if contains_forbidden_link(message.content, self.whitelisted_domains):
        #     moderation_reason = "Partilha de links não autorizados"
        
        if not moderation_reason:
            moderation_reason = find_forbidden_content(message.content, self.forbidden_words, "Uso de linguagem/tópico proibido")

        if not moderation_reason:
            moderation_reason = find_forbidden_content(message.content, self.forbidden_memecoins, "Menção de memecoins não é permitida")

        if moderation_reason:
            await self.trigger_moderation_action(message, moderation_reason)
            return

    async def trigger_moderation_action(self, message, reason: str):
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

        if self.hugo_user:
            alert_text_hugo = (
                f"## Alerta de Moderação (Bits)\n\n"
                f"**Utilizador:** {author.name} (`{author.id}`)\n"
                f"**Ação:** Mensagem eliminada\n"
                f"**Motivo:** {reason}\n"
                f"**Conteúdo da Mensagem:**\n> {message.content}"
            )
            try:
                await self.hugo_user.send(alert_text_hugo)
            except discord.errors.Forbidden:
                print(f"FEHLER: Konnte keine DM an Hugo senden.")
        
        print(f"Aktion durchgeführt: Nachricht von {author.name} wegen '{reason}' gelöscht.")

async def setup_moderator(bot):
    await bot.add_cog(ModeratorCog(bot))
    print("Moderator-Modul erfolgreich geladen.")
