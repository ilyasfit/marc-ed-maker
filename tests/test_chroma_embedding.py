import os
import sys
import asyncio
import logging

# Add the project root to the path so we can import shared modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shared import config
from knowledge.vector_store import EmbeddingManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    if not config.OPENAI_API_KEY:
        print("WARNUNG: Kein OpenAI API Key gefunden. Das Skript wird fehlschlagen, wenn es versucht zu embedden.")
    
    print("Initializing Embedding Manager...")
    # Use a separate DB path for testing if desired, or the same one
    # For this test, let's use the production one to verify it works
    manager = EmbeddingManager()
    
    print("--- Starting Synchronization ---")
    manager.sync_knowledge_base()
    print("--- Synchronization Complete ---")
    
    # Test Query
    test_query = "Was ist das Fibonacci Retracement?"
    print(f"\n--- Testing Query: '{test_query}' ---")
    context = manager.query_context(test_query)
    print("Retrieved Context:")
    print(context[:500] + "..." if len(context) > 500 else context)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ImportError as e:
        print(f"Test failed due to missing dependencies: {e}")
        print("Please ensure 'chromadb' is installed.")
    except Exception as e:
        print(f"An error occurred: {e}")
