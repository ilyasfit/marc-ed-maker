import logging
import asyncio
from datetime import datetime
from openai import AsyncOpenAI
from shared import config

# Ensure logger is configured
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(module)s - %(message)s')

# Configure xAI Client (using OpenAI SDK compatibility)
if config.XAI_API_KEY:
    try:
        xai_client = AsyncOpenAI(
            api_key=config.XAI_API_KEY,
            base_url="https://api.x.ai/v1"
        )
        logging.info("xAI API Client configured successfully.")
    except Exception as e:
        logging.critical(f"Critical error configuring xAI Client: {e}.")
        xai_client = None
else:
    logging.warning("No xAI API Key found in configuration.")
    xai_client = None

# Use grok-beta or grok-2 as default
XAI_MODEL_NAME = "grok-beta"

async def get_xai_response(user_query: str, context_data: str, system_instruction_override: str = None) -> str:
    """
    Sends a request to the xAI API and returns the text response.
    """
    if not xai_client:
        logging.error("Attempt to call xAI without valid client.")
        return "Error: xAI API is not configured."

    try:
        final_system_instruction = system_instruction_override if system_instruction_override else "You are Grok, a chatbot inspired by the Hitchhiker's Guide to the Galaxy."
        
        # Prepare messages
        messages = [
            {"role": "system", "content": final_system_instruction}
        ]

        if context_data:
            context_message = (
                "--- BEGIN PROVIDED CONTEXT ---\n"
                f"{context_data}\n"
                "--- END PROVIDED CONTEXT ---\n"
            )
            messages.append({"role": "system", "content": context_message})

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        messages.append({"role": "system", "content": f"Current Date and Time: {current_time}"})
        
        messages.append({"role": "user", "content": user_query})

        logging.info(f"Sending request to xAI model '{XAI_MODEL_NAME}'.")

        # Note: To use web search, we might need to add tools=[...] here if xAI supports it via OpenAI SDK.
        # Current research suggests specific SDK or tool definitions are needed.
        # For now, we use standard chat completion.
        
        response = await xai_client.chat.completions.create(
            model=XAI_MODEL_NAME,
            messages=messages,
            stream=False 
        )

        choice = response.choices[0]
        content = choice.message.content
        
        logging.info(f"Received response from xAI. Finish reason: {choice.finish_reason}. Length: {len(content) if content else 0}")
        
        if not content:
             return "I'm sorry, I received an empty response from xAI."

        return content.strip()

    except Exception as e:
        logging.error(f"Error communicating with xAI API: {e}", exc_info=True)
        return f"Error communicating with xAI: {e}"
