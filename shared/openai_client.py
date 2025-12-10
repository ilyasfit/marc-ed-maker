import logging
import asyncio
from datetime import datetime
from openai import AsyncOpenAI
from shared import config

# Ensure logger is configured
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(module)s - %(message)s')

# Configure OpenAI Client
if config.OPENAI_API_KEY:
    try:
        openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        logging.info("OpenAI API Client configured successfully.")
    except Exception as e:
        logging.critical(f"Critical error configuring OpenAI Client: {e}.")
        openai_client = None
else:
    logging.warning("No OpenAI API Key found in configuration.")
    openai_client = None

OPENAI_MODEL_NAME = "gpt-5-mini"

async def get_openai_response(user_query: str, context_data: str, system_instruction_override: str = None) -> str:
    """
    Sends a request to the OpenAI API and returns the text response.
    """
    if not openai_client:
        logging.error("Attempt to call OpenAI without valid client.")
        return "Error: OpenAI API is not configured."

    try:
        final_system_instruction = system_instruction_override if system_instruction_override else config.GEMINI_SYSTEM_INSTRUCTION
        
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

        logging.info(f"Sending request to OpenAI model '{OPENAI_MODEL_NAME}'.")

        response = await openai_client.chat.completions.create(
            model=OPENAI_MODEL_NAME,
            messages=messages
            # max_completion_tokens removed to allow full model capacity/defaults
        )

        choice = response.choices[0]
        content = choice.message.content
        
        # Enhanced logging for debugging empty responses
        logging.info(f"Received response from OpenAI. Finish reason: {choice.finish_reason}. Length (chars): {len(content) if content else 0}")
        
        if not content:
             logging.warning(f"Empty content received. Full choice object: {choice}")
             if hasattr(choice.message, 'refusal') and choice.message.refusal:
                 return f"The AI refused to answer: {choice.message.refusal}"
             if choice.finish_reason == 'content_filter':
                 return "The response was filtered due to safety content policies."
             return "I'm sorry, I received an empty response from the AI."

        return content.strip()

    except Exception as e:
        logging.error(f"Error communicating with OpenAI API: {e}", exc_info=True)
        if "rate_limit" in str(e).lower():
             return "I'm currently receiving too many requests. Please try again later."
        elif "context_length" in str(e).lower():
             return " The context is too long for the model to process."
        
        return "I need to rest for a moment. Please ask me again in about a minute!"
