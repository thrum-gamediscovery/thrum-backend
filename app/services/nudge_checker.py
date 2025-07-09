"""
📄 File: app/services/nudge_checker.py
Checks sessions for inactivity after Thrum speaks and sends a gentle nudge.
Also detects tone-shift (e.g., cold or dry replies).
"""

from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.db.models.session import Session
from app.utils.whatsapp import send_whatsapp_message
from app.db.models.enums import SenderEnum, PhaseEnum
import random
import openai

# 🧠 GPT-based tone detection
async def detect_user_is_cold(session, db) -> bool:
    user_msgs = [i for i in session.interactions if i.sender == SenderEnum.User][-3:]
    if len(user_msgs) < 2:
        return False

    dry_like_count = 0
    for i in user_msgs:
        prompt = f"""
You are a tone detector. Classify the tone of this message into one of:
[chill, chaotic, dry, genz, formal, emotional, closed, neutral]

Message: "{i.content}"
Respond with one word only.
"""
        try:
            res = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            label = res["choices"][0]["message"]["content"].strip().lower()
            if label in ["dry", "closed", "neutral"]:
                dry_like_count += 1
        except:
            continue

    return dry_like_count >= 2

async def check_for_nudge():
    db = SessionLocal()
    now = datetime.utcnow()
    sessions = db.query(Session).filter(Session.awaiting_reply == True, Session.phase != PhaseEnum.ENDING).all()

    for s in sessions:
        user = s.user
        if not s.last_thrum_timestamp:
            continue

        # ⏱️ Adaptive delay based on silence count
        delay = timedelta(seconds=60)

        if now - s.last_thrum_timestamp > delay:
            # 🎯 Soft nudge message
            nudge = random.choice([
                "Still there? 😊",
                "Just drop a word, I’m here.",
                "You can say anything — no pressure.",
                "Take your time. I’m listening.",
                "Feel free to toss in a mood or thought.",
                "Whenever you’re ready, just type something.",
                "No rush — I’m right here when you are.",
                "Say anything — a vibe, a genre, a name.",
                "Let’s keep this going when you’re ready!"
            ])
            await send_whatsapp_message(user.phone_number, nudge)

            # 🧠 Track nudge + potential coldness
            s.awaiting_reply = False
            user.silence_count = (user.silence_count or 0) + 1
            
            db.commit()

    db.close()
