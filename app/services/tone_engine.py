import re
import openai
from app.db.session import SessionLocal
from app.db.models.session import Session as DBSession

# tone → reply style mapping
TONE_STYLE_MAP = {
    "genz": "gen_z",
    "casual": "chill",
    "warm": "chill",
    "sincere": "chill",
    "chaotic": "gen_z",
    "funny": "gen_z",
    "defiant": "gen_z",
    "excited": "gen_z",
    "closed": "dry",
    "ironic": "dry",
    "neutral": "neutral",
    "open": "neutral",
}

def apply_tone_style(reply: str, tone: str) -> str:
    if tone == "gen_z":
        reply = reply.replace(".", "!") + " 🔥"
    elif tone == "chill":
        reply = reply.replace("!", ".").lower().capitalize()
    elif tone == "dry":
        reply = re.sub(r"[!\\.]", "", reply).split(".")[0] + "."
    return reply

async def detect_tone_cluster(db, session, user_input: str) -> str:
    """
    Uses GPT to detect the user's tone and maps it to a tone cluster.
    """
    prompt = f"""
You are a tone detector for a conversational assistant.
Classify the user's message below into one of these tone clusters:
[genz, chaotic, sincere, ironic, casual, neutral, warm, open, closed, funny, defiant, excited]

Message: \"{user_input}\"

Only respond with ONE WORD that best describes the tone. No punctuation.
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        tone = response["choices"][0]["message"]["content"].strip().lower()
        tone = tone.split()[0]  # In case GPT adds anything extra
    except Exception as e:
        print(f"⚠️ Tone detection failed: {e}")
        tone = "neutral"

    return tone

async def tone_match_validator(reply: str, user_id: str, user_input: str, db) -> str:
    try:
        gpt_tone = await detect_tone_cluster(db, None, user_input)
        mapped_tone = TONE_STYLE_MAP.get(gpt_tone, "neutral")
    except Exception:
        mapped_tone = "neutral"

    store_user_tone(user_id, mapped_tone)
    return apply_tone_style(reply, mapped_tone)

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
    finally:
        db.close()
