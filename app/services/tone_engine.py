import re
import openai
from app.db.session import SessionLocal
from app.db.models.session import Session as DBSession

# GPT tone → internal style
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

def apply_tone_style(reply: str, tone: str) -> str:
    """
    Adjusts Thrum's final reply based on detected tone.
    """
    if tone == "gen_z":
        reply = reply.replace(".", "!") + " 🔥"
    elif tone == "chill":
        reply = reply.replace("!", ".").capitalize()
    elif tone == "dry":
        reply = re.sub(r"[!]", "", reply).strip().split(".")[0].strip() + "."
    return reply

async def detect_tone_cluster(db, session, user_input: str) -> str:
    """
    Uses GPT to classify the user's tone based on latest input.
    """
    prompt = f"""
You are a tone detector for a conversational assistant.
Classify the user's message below into one of these tone clusters:
[genz, chaotic, sincere, ironic, casual, neutral, warm, open, closed, funny, defiant, excited]

Message: "{user_input}"

Only respond with ONE WORD that best describes the tone. No punctuation.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        tone = response["choices"][0]["message"]["content"].strip().lower().split()[0]
        print(f"🎯 Detected tone cluster: {tone}")
    except Exception as e:
        print(f"⚠️ Tone detection failed: {e}")
        tone = "neutral"

    return tone

async def tone_match_validator(reply: str, user_id: str, user_input: str, db) -> str:
    """
    Detects user's tone and adjusts reply to match it.
    """
    try:
        gpt_tone = await detect_tone_cluster(db, None, user_input)
        mapped_tone = TONE_STYLE_MAP.get(gpt_tone, "neutral")
        print(f"✅ Tone applied: {mapped_tone} (from GPT tone: {gpt_tone})")
    except Exception as e:
        print(f"⚠️ Tone validation fallback: {e}")
        mapped_tone = "neutral"

    store_user_tone(user_id, mapped_tone)
    return apply_tone_style(reply, mapped_tone)

def store_user_tone(user_id: str, tone: str):
    """
    Stores tone in the most recent session's meta_data for reuse.
    """
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
