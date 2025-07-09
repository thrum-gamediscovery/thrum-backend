import re
import openai
from datetime import datetime
from app.db.session import SessionLocal
from app.db.models.session import Session as DBSession
from app.db.models.enums import SenderEnum

# 🧠 Extract latest user tone from session.interactions
def get_last_user_tone_from_session(session) -> str:
    if not session or not session.interactions:
        return "neutral"

    user_interactions = [i for i in session.interactions if i.sender == SenderEnum.User]
    if not user_interactions:
        return "neutral"

    return user_interactions[-1].tone_tag or "neutral"

# GPT tone → internal style mapping
TONE_STYLE_MAP = {
    "genz": "gen_z",
    "chaotic": "gen_z",
    "funny": "gen_z",
    "defiant": "gen_z",
    "excited": "gen_z",
    "casual": "chill",
    "warm": "chill",
    "sincere": "chill",
    "closed": "dry",
    "ironic": "dry",
    "neutral": "neutral",
    "open": "neutral"
}

# 🔥 Gen-Z Slang Generator
async def generate_genz_slang_line(base_reply: str) -> str:
    prompt = f"""
You are a Gen-Z slang generator helping a game recommender sound witty and relatable.
Given this response: "{base_reply}", add a short Gen-Z-style phrase at the end.
It should sound playful or confident, like "this one slaps" or "bet".
Return only the phrase. No emojis. Max 5 words.
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=12,
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"⚠️ Gen-Z phrase generation failed: {e}")
        return ""

# 🪄 Modular reply transformers by tone
def replace_punctuation(exclamation=False):
    def inner(text):
        return text.replace(".", "!") if exclamation else text.replace("!", ".")
    return inner

def add_flame():
    return lambda text: text.strip() + " 🔥"

def soften_and_capitalize():
    return lambda text: text.lower().capitalize()

def flatten_sentence():
    return lambda text: re.sub(r"[!\\.]", "", text).split(".")[0] + "."

TONE_TRANSFORMS = {
    "gen_z": [replace_punctuation(exclamation=True), add_flame()],
    "chill": [replace_punctuation(exclamation=False), soften_and_capitalize()],
    "dry": [flatten_sentence()],
}

def apply_tone_style(reply: str, session) -> str:
    """
    Apply tone transforms based on recent tone history stored in session.
    Falls back to the latest tone in session.meta_data['tone'].
    """
    history = session.meta_data.get("tone_history", [])
    tone = history[-1] if history else session.meta_data.get("tone")

    if not tone:
        return reply  # No tone to apply

    for transform in TONE_TRANSFORMS.get(tone, []):
        reply = transform(reply)

    return reply

# 🎯 Optional Gen-Z slang injection
async def get_response_style(tone: str, reply: str) -> str:
    if tone != "gen_z":
        return reply
    if re.search(r"\b(sorry|apologies|let me check)\b", reply, re.IGNORECASE):
        return reply  # don't slangify fallback answers

    if re.search(r"[a-zA-Z]", reply) and "." in reply:
        phrase = await generate_genz_slang_line(reply)
        if phrase:
            parts = reply.split(".")
            parts[-2] += f" — {phrase}"
            reply = ".".join(parts)
    return reply

# 🧠 GPT-Based Tone Detection
async def detect_tone_cluster(user_input: str) -> str:
    prompt = f"""
You are a tone classifier.

Classify the tone of this message into one of:
[genz, chaotic, sincere, ironic, casual, neutral, warm, open, closed, funny, defiant, excited]

Consider:
- Language style (slang, punctuation, emojis, length)
- Emotional energy (lowkey, honest, hyped, distant, bold)
- Vibe (friendly, dry, loud, short, quirky, chill)
- if there is genz word then pass the tone genz.
- analyse given all tone and return most relevant.
Message: "{user_input}"

Only respond with ONE WORD that best describes the tone. No punctuation.
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        tone = response["choices"][0]["message"]["content"].strip().lower().split()[0]
        print(f"🎯 Detected tone cluster: {tone}")
    except Exception as e:
        print(f"⚠️ Tone detection failed: {e}")
        tone = "neutral"
    return tone

# 🎛️ Final Tone Validator + Styling
async def tone_match_validator(reply: str, user_id: str, user_input: str, db, session) -> str:
    try:
        gpt_tone = await detect_tone_cluster(user_input)
        mapped_tone = TONE_STYLE_MAP.get(gpt_tone, "neutral")
        print(f"✅ Tone applied: {mapped_tone} (from GPT: {gpt_tone})")
    except Exception as e:
        print(f"⚠️ Tone validation fallback: {e}")
        mapped_tone = "neutral"

    store_user_tone(user_id, mapped_tone)
    update_tone_in_history(session, mapped_tone)
    styled_reply = apply_tone_style(reply, session)
    final_reply = await get_response_style(mapped_tone, styled_reply)
    return final_reply

# 💾 Store tone in session meta
def store_user_tone(user_id: str, tone: str):
    db = SessionLocal()
    try:
        session = (
            db.query(DBSession)
            .filter(DBSession.user_id == user_id)
            .order_by(DBSession.start_time.desc())
            .first()
        )
        if session:
            session.meta_data = session.meta_data or {}
            session.meta_data["tone"] = tone
            db.commit()
            print(f"💾 Stored tone '{tone}' for user {user_id}")
    except Exception as e:
        print(f"⚠️ Failed to store tone: {e}")
    finally:
        db.close()

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