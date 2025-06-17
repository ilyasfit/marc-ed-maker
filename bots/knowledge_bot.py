import discord
from discord.ext import commands
from shared import config, gemini_client
import os

class KnowledgeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.context_data = self.load_context_data()

    def load_context_data(self):
        """
        Lädt rekursiv alle .txt- und .md-Dateien aus dem QNA_CONTEXT_PATH
        und gibt deren kombinierten Inhalt als einzelnen String zurück.
        """
        combined_parts = []
        if not os.path.isdir(config.QNA_CONTEXT_PATH):
            print(f"WARNUNG: Q&A-Kontextverzeichnis nicht gefunden: {config.QNA_CONTEXT_PATH}")
            return ""
        
        for root, _, files in sorted(os.walk(config.QNA_CONTEXT_PATH)):
            for filename in sorted(files):
                if filename.endswith((".txt", ".md")):
                    filepath = os.path.join(root, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            combined_parts.append(f.read())
                    except Exception as e:
                        print(f"FEHLER: Konnte die Kontextdatei nicht lesen: {filepath} - {e}")
                        
        return "\n\n---\n\n".join(combined_parts)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user or message.guild is None:
            return

        is_target_channel = not config.QNA_TARGET_CHANNEL_IDS or message.channel.id in config.QNA_TARGET_CHANNEL_IDS
        bot_mentioned = self.bot.user.mentioned_in(message)

        if not (is_target_channel and bot_mentioned):
            return

        # Check if the message is from the moderator cog
        if await self.bot.get_cog('ModeratorCog').on_message(message):
            return

        async with message.channel.typing():
            query = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            
            response = await gemini_client.get_gemini_response(query, self.context_data)

            is_first_message = True
            for i in range(0, len(response), 2000):
                chunk = response[i:i+2000]
                if is_first_message:
                    await message.reply(chunk)
                    is_first_message = False
                else:
                    await message.channel.send(chunk)

async def setup_knowledge_bot(bot):
    await bot.add_cog(KnowledgeCog(bot))
    print("Knowledge-Bot-Modul erfolgreich geladen.")
