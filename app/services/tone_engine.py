import re
import os
import openai
from datetime import datetime
from app.db.session import SessionLocal
from app.db.models.session import Session as DBSession
from app.db.models.enums import SenderEnum
from openai import AsyncOpenAI

client = AsyncOpenAI()

model= os.getenv("GPT_MODEL")

# 🧠 Extract latest user tone from session.interactions
def get_last_user_tone_from_session(session) -> str:
    if not session or not session.interactions:
        return "neutral"

    user_interactions = [i for i in session.interactions if i.sender == SenderEnum.User]
    if not user_interactions:
        return "neutral"

    return user_interactions[-1].tone_tag or "neutral"

# 🧠 GPT-Based Tone Detection
async def detect_tone_cluster(user_input: str) -> str:
    allowed_tags = {
        "genz", "chaotic", "sincere", "ironic", "casual", "neutral", "warm", "open", "closed",
        "funny", "defiant", "excited", "frustrated", "bored", "angry", "satisfied", "confused", "sad"
    }

    prompt = f"""
        Classify the tone of this user message based on both emotion and style.

        Choose ONE or a COMBINATION (max 2) from:
        [genz, chaotic, sincere, ironic, casual, neutral, warm, open, closed, funny, defiant, excited, frustrated, bored, angry, satisfied, confused, sad]

        Rules:
        - If slang, emojis, or hype → tag genz
        - If tone is frustrated *and* genz → return "genz frustrated"
        - If tone is unsure or irritated → tag confused or frustrated
        - If short, dry replies like "ok", "fine", or "hello?" → bored or frustrated
        - If joyful or thankful → satisfied or excited
        - If style is unclear → return neutral

        Message: "{user_input}"

        Only return ONE or TWO words (space-separated). No punctuation.
        """
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        
        tone = response.choices[0].message.content.strip().lower()
        tone = tone.replace(".", "").replace(",", "")  # Remove any punctuation

        words = [w for w in tone.split() if w in allowed_tags]
        if not words:
            tone = "neutral"
        elif len(words) > 2:
            tone = " ".join(words[:2])
        else:
            tone = " ".join(words)
        
        print(f"🎯 Detected tone cluster: {tone}")
    except Exception as e:
        print(f"⚠️ Tone detection failed: {e}")
        tone = "neutral"
    return tone

def update_tone_in_history(session, tone: str):
    try:
        # Ensure that meta_data and tone_history exist
        session.meta_data = session.meta_data or {}
        session.meta_data["tone_history"] = session.meta_data.get("tone_history", [])

        # Update the last entry in tone_history with the new tone and timestamp
        if session.meta_data["tone_history"]:
            # Replace the last entry in the list
            session.meta_data["tone_history"][-1] = {
                "tone": tone,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            # If tone_history is empty, initialize it with the first entry
            session.meta_data["tone_history"].append({
                "tone": tone,
                "timestamp": datetime.utcnow().isoformat()
            })

    except Exception as e:
        # Handle errors gracefully
        print(f"Error updating tone in history: {e}")