import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shared import config, xai_client

async def test_xai_connection():
    print("Testing xAI Connection...")
    if not config.XAI_API_KEY:
        print("SKIPPING: No XAI_API_KEY found in env.")
        return

    query = "What is the price of Bitcoin right now? Please use your search capabilities if possible."
    context = "Context: This is a test."
    
    print(f"Query: {query}")
    response = await xai_client.get_xai_response(query, context)
    print("Response:")
    print(response)
    print("-" * 20)

    # Test "Fundamental Analysis" prompt logic roughly
    print("Testing Analysis Prompt...")
    analysis_query = "Conduct a brief fundamental analysis of Ethereum for this week."
    response_analysis = await xai_client.get_xai_response(analysis_query, "")
    print("Response Analysis:")
    print(response_analysis[:500] + "..." if len(response_analysis) > 500 else response_analysis)

if __name__ == "__main__":
    asyncio.run(test_xai_connection())
