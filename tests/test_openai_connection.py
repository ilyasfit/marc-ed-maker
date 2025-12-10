import os
import sys

# Add project root to path to allow importing from shared
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

def test_openai_connection():
    print("--- OpenAI API Connection Test ---")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not found in .env file.")
        print("Please add OPENAI_API_KEY=your-key-here to your .env file.")
        return

    print(f"API Key found: {api_key[:5]}...{api_key[-4:]}")
    
    try:
        client = OpenAI(api_key=api_key)
        
        print("Sending request to OpenAI (model: gpt-5-mini)...")
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"}
            ],
            max_completion_tokens=150
        )
        
        content = response.choices[0].message.content
        print("\nResponse received:")
        print(f"'{content}'")
        
        if not content:
             print("\nWARNING: Received empty response. This might happen with very short max_completion_tokens or specific model behavior.")
        
        print("\nSUCCESS: OpenAI API connection validated.")
        
    except Exception as e:
        print(f"\nFAILURE: An error occurred: {e}")
        if "model_not_found" in str(e):
            print("Tip: Check if 'gpt-5-mini' is available for your API key.")
        elif "authentication_error" in str(e):
            print("Tip: Check if your API key is correct.")

if __name__ == "__main__":
    test_openai_connection()
