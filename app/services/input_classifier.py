import openai
import os
import json
from openai import OpenAIError
from app.db.models.session import Session

# Set API Key
openai.api_key = os.getenv("OPENAI_API_KEY")



import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

async def is_intent_override(user_input: str) -> bool:
    """
    Uses GPT to decide if the user is overriding intent and wants a game immediately.

    Returns True if GPT believes the message skips discovery and demands a direct game.
    """

    prompt = (
        "You are a classification agent for a game recommendation bot.\n"
        "Your task is to detect if the user's message is a direct request for a game,\n"
        "bypassing all mood/genre/platform questions (called an 'intent override').\n\n"
        f"User message: \"{user_input}\"\n\n"
        "Is this an intent override?\n"
        "Respond with just: true or false."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            temperature=0,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        content = response['choices'][0]['message']['content'].strip().lower()
        return "true" in content

    except Exception as e:
        print("GPT override check failed:", e)
        return False
    
# ✅ Use OpenAI to classify mood, vibe, genre, and platform from free text
async def classify_user_input(session: Session, user_input: str) -> dict | str:
    """
    Takes raw user input and uses OpenAI to extract mood, genre, platform preferences.

    Returns a dictionary like:
    {
        "mood": "cozy",
        "genre": "puzzle",
        "platform": "Steam"
    }

    On failure, returns a string with error message.
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            temperature=0.4,
            messages=[
                {"role": "system", "content": "You are a game recommendation assistant. Extract game preferences from the user's message."},
                {"role": "user", "content": f"User said: {user_input}. Extract mood, genre, and platform as JSON."}
            ]
        )

        content = response['choices'][0]['message']['content']
        result = json.loads(content)
        return result  # should be a dict with mood, genre, platform

    except (OpenAIError, json.JSONDecodeError) as e:
        return f"❌ Classification error: {str(e)}"
