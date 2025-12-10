import discord
from discord.ext import commands
from shared import config, gemini_client, openai_client
import os
import asyncio
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Try to import EmbeddingManager
try:
    from knowledge.vector_store import EmbeddingManager
    HAS_VECTOR_STORE = True
except ImportError as e:
    logger.error(f"Could not import EmbeddingManager: {e}. Vector Store functionality will be disabled.")
    HAS_VECTOR_STORE = False

class KnowledgeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embedding_manager = None
        self.context_data = "" # Fallback
        
        if HAS_VECTOR_STORE:
            try:
                self.embedding_manager = EmbeddingManager()
            except Exception as e:
                logger.error(f"Failed to initialize EmbeddingManager: {e}")
        else:
            # Fallback to old method if vector store fails
            self.context_data = self.load_context_data_legacy()

    async def cog_load(self):
        """Asynchronous initialization hook called when the cog is loaded."""
        if HAS_VECTOR_STORE:
            try:
                # Use asyncio.get_running_loop() to be safe
                loop = asyncio.get_running_loop()
                
                # Offload initialization to thread to avoid blocking loop and any sync/async loop weirdness
                self.embedding_manager = await loop.run_in_executor(None, EmbeddingManager)
                
                # Start background sync
                loop.create_task(self.sync_knowledge_base())
            except Exception as e:
                logger.error(f"Failed to initialize EmbeddingManager in cog_load: {e}")
                # Ensure legacy context fallback if init failed
                if not self.context_data:
                     # Use loop.run_in_executor to keep it async friendly
                     self.context_data = await loop.run_in_executor(None, self.load_context_data_legacy)

    async def sync_knowledge_base(self):
        """Runs the knowledge base synchronization in a separate thread."""
        logger.info("Starting background knowledge base sync...")
        if not self.embedding_manager:
            logger.warning("Embedding manager not initialized, skipping sync.")
            return

        try:
            # Run in executor to not block the main loop
            await self.bot.loop.run_in_executor(None, self.embedding_manager.sync_knowledge_base)
            logger.info("Background knowledge base sync finished.")
        except Exception as e:
            logger.error(f"Error during background knowledge base sync: {e}")

    def load_context_data_legacy(self):
        """
        Legacy: Lädt rekursiv alle .txt- und .md-Dateien aus dem QNA_CONTEXT_PATH
        und gibt deren kombinierten Inhalt als einzelnen String zurück.
        """
        combined_parts = []
        if not os.path.isdir(config.QNA_CONTEXT_PATH):
            logger.warning(f"WARNUNG: Q&A-Kontextverzeichnis nicht gefunden: {config.QNA_CONTEXT_PATH}")
            return ""
        
        for root, _, files in sorted(os.walk(config.QNA_CONTEXT_PATH)):
            for filename in sorted(files):
                if filename.endswith((".txt", ".md")):
                    filepath = os.path.join(root, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            combined_parts.append(f.read())
                    except Exception as e:
                        logger.error(f"FEHLER: Konnte die Kontextdatei nicht lesen: {filepath} - {e}")
                        
        return "\n\n---\n\n".join(combined_parts)

    def load_static_context(self):
        """
        Loads static context files from the 'static' subdirectory of QNA_CONTEXT_PATH.
        """
        static_context = []
        static_path = os.path.join(config.QNA_CONTEXT_PATH, 'static')
        
        if not os.path.exists(static_path):
            # Creates directory if it doesn't exist to allow drag-n-drop
            try:
                os.makedirs(static_path, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create static context directory: {e}")
            return ""

        for root, _, files in sorted(os.walk(static_path)):
            for filename in sorted(files):
                if filename.endswith((".txt", ".md")):
                    filepath = os.path.join(root, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            static_context.append(f.read())
                    except Exception as e:
                        logger.error(f"Failed to read static context file {filepath}: {e}")
        
        return "\n\n---\n\n".join(static_context)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user or message.guild is None:
            return

        is_target_channel = not config.QNA_TARGET_CHANNEL_IDS or message.channel.id in config.QNA_TARGET_CHANNEL_IDS
        bot_mentioned = self.bot.user.mentioned_in(message)

        if not (is_target_channel and bot_mentioned):
            return

        # Check if the message is from the moderator cog
        # Safely get cog to avoid AttributeError if it's not loaded yet
        mod_cog = self.bot.get_cog('ModeratorCog')
        if mod_cog and await mod_cog.on_message(message):
            return

        async with message.channel.typing():
            query = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            
            # Retrieve context
            vector_context = ""
            if self.embedding_manager:
                # Query Vector DB
                # Run query in executor to avoid blocking
                vector_context = await self.bot.loop.run_in_executor(
                    None, 
                    lambda: self.embedding_manager.query_context(query)
                )
            
            # Load static context
            static_context = await self.bot.loop.run_in_executor(None, self.load_static_context)
            
            # Construct Final Prompt Structure
            from datetime import datetime
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            final_context = f"Aktuelles Datum: {current_date}\n\n"
            final_context += "INSTRUKTION AN DAS SYSTEM:\n"
            final_context += "Nutze die folgenden Informationen als dein alleiniges Wissensarchiv. Ignoriere Internetwissen, wenn es den unten stehenden Regeln widerspricht.\n\n"
            final_context += "--- BEGINN DES BEREITGESTELLTEN KONTEXTES ---\n\n"
            
            if vector_context:
                final_context += f"{vector_context}\n\n"
                
            final_context += "---\n\n"
            
            if static_context:
                final_context += f"{static_context}\n\n"
                
            final_context += "(WICHTIG: Hier müssen die Links exakt so stehen wie in deinem Beispiel, damit der Bot sie \"kopieren\" kann)\n\n"
            final_context += "--- ENDE DES BEREITGESTELLTEN KONTEXTES ---\n\n"
            
            # Note: The User Query is appended by the LLM Client usually, but based on your request structure,
            # you might want to format it here explicitly if the client just takes a prompt string.
            # However, openai_client.get_openai_response typically takes (query, context).
            # We will pass this constructed 'final_context' as the context argument.
            
            if not vector_context and not static_context and not self.embedding_manager:
                 final_context = self.context_data # Fallback
            
            # Log retrieval for debugging
            logger.info(f"Retrieved Context Length: Vector={len(vector_context)}, Static={len(static_context)}")

            # Select LLM based on config
            response = ""
            if config.LLM_PROVIDER.lower() == 'gemini':
                response = await gemini_client.get_gemini_response(query, final_context)
            else: # Default to OpenAI
                if config.OPENAI_API_KEY:
                     response = await openai_client.get_openai_response(query, final_context)
                elif config.GEMINI_API_KEY:
                     logger.warning("OpenAI configured as provider but no key found. Falling back to Gemini.")
                     response = await gemini_client.get_gemini_response(query, final_context)
                else:
                     response = "Fehler: Kein gültiger LLM Provider konfiguriert (weder OpenAI noch Gemini Keys gefunden)."

            is_first_message = True
            if response:
                for i in range(0, len(response), 2000):
                    chunk = response[i:i+2000]
                    if is_first_message:
                        await message.reply(chunk)
                        is_first_message = False
                    else:
                        await message.channel.send(chunk)
            else:
                await message.reply("Entschuldigung, ich konnte keine Antwort generieren.")

async def setup_knowledge_bot(bot):
    await bot.add_cog(KnowledgeCog(bot))
    print("Knowledge-Bot-Modul erfolgreich geladen.")
