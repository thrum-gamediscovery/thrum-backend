import re
import os
import openai
from datetime import datetime
from app.db.models.enums import SenderEnum
from openai import AsyncOpenAI

client = AsyncOpenAI()

model= os.getenv("GPT_MODEL")

# 🧠 Extract latest user tone from session.interactions
async def get_last_user_tone_from_session(session) -> str:
    if not session or not session.interactions:
        return "neutral"

    user_interactions = [i for i in session.interactions if i.sender == SenderEnum.User]
    if not user_interactions:
        return "neutral"

    return user_interactions[-1].tone_tag or "neutral"

# 🧠 GPT-Based Tone Detection
async def detect_tone_cluster(user_input: str):
    TONE_CLUSTERS = ["neutral", "casual", "warm", "sincere", "polite", "friendly", "playful", "sarcastic", "excited", "enthusiastic", "confused", "curious", "vague", "bored", "cold", "formal", "cautious", "cheerful", "grateful", "apologetic", "impatient", "annoyed", "frustrated", "dismissive", "assertive", "encouraging", "optimistic", "pessimistic", "disengaged", "empathetic", "genz", "vibey", "edgy", "hyped"]

    prompt = f"""
        You are an expert in analyzing conversational tone for chatbots.
        Given the following user message, reply with the most likely tone *cluster* from this list only: {TONE_CLUSTERS}.
        If uncertain, output 'neutral'.
        Reply in the format: tone_tag: <tone> | confidence: <score from 0.0 to 1.0>
        User message:
        \"\"\"{user_input}\"\"\"
        Rules:
        - If slang, emojis, or hype → tag genz
        - If tone is frustrated *and* genz → return "genz frustrated"
        - If tone is unsure or irritated → tag confused or frustrated
        - If short, dry replies like "ok", "fine", or "hello?" → bored or frustrated
        - If joyful or thankful → satisfied or excited
        - If style is unclear → return neutral

        Only return ONE or TWO words (space-separated). No punctuation.
        """
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = response.choices[0].message.content
        output = content.strip() if content else "neutral"
    except Exception as e:
        # Fallback in case LLM call fails
        return "neutral", 0.5
    m = re.search(r"tone_tag:\s*([a-zA-Z_]+)\s*\|\s*confidence:\s*([0-9.]+)", output)
    if m:
        tone_tag = m.group(1).lower()
        try:
            confidence = float(m.group(2))
        except ValueError:
            confidence = 0.7
    else:
        # Fallback if format is wrong
        tone_tag = "neutral"
        confidence = 0.5

    # Enforce valid cluster
    if tone_tag not in TONE_CLUSTERS and tone_tag != "neutral":
        tone_tag = "neutral"
        confidence = 0.5

    return tone_tag, confidence

def update_tone_in_history(session, tone: str, confidence):
    try:
        # Ensure that meta_data and tone_history exist
        session.meta_data = session.meta_data or {}
        session.meta_data["tone_history"] = session.meta_data.get("tone_history", [])
        session.meta_data["tone"] = tone
        
        # Update the last entry in tone_history with the new tone and timestamp
        if session.meta_data["tone_history"]:
            # Replace the last entry in the list
            session.meta_data["tone_history"][-1] = {
                "tone": tone,
                "confidence": confidence,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            # If tone_history is empty, initialize it with the first entry
            session.meta_data["tone_history"].append({
                "tone": tone,
                "confidence": confidence,
                "timestamp": datetime.utcnow().isoformat()
            })

    except Exception as e:
        # Handle errors gracefully
        print(f"Error updating tone in history: {e}")