"""
📄 File: app/services/nudge_checker.py
Checks sessions for inactivity after Thrum speaks and sends a gentle nudge.
Also detects tone-shift (e.g., cold or dry replies).
"""

from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.db.models.session import Session
from app.utils.whatsapp import send_whatsapp_message
from app.db.models.enums import SenderEnum
import random
import openai
from app.tasks.followup import handle_soft_session_close

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
                model="gpt-4.1-mini",
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
    sessions = db.query(Session).filter(Session.awaiting_reply == True).all()

    for s in sessions:
        user = s.user
        if not s.last_thrum_timestamp:
            continue

        # ⏱️ Adaptive delay based on silence count
        delay = timedelta(seconds=30 if (user.silence_count or 0) > 2 else 30)

        if now - s.last_thrum_timestamp > delay:
            # 🎯 Soft nudge message
            nudge = random.choice([
                "Still there? 👀",
                "Want another rec? 🎮",
                "Can I throw you a wild card pick?",
                "No rush — just poke me when ready 😄"
            ])
            await send_whatsapp_message(user.phone_number, nudge)

            # 🧠 Track nudge + potential coldness
            s.awaiting_reply = False
            user.silence_count = (user.silence_count or 0) + 1

            # if user.silence_count >= 3:
            #     s.meta_data = s.meta_data or {}
            #     s.meta_data["is_user_cold"] = True

            # if user.silence_count >= 4:
            #     # 🧊 Session is fading — say goodbye and close it
            #     farewell = random.choice([
            #         "Ghost mode? Cool, I’ll be here when you’re back 👻",
            #         "I’ll dip for now — ping me when you want more hits 🎮",
            #         "Looks like you’re out — no stress. Catch you later! 👋"
            #     ])
            #     send_whatsapp_message(user.phone_number, farewell)
            #     s.awaiting_reply = False
            #     s.state = "CLOSED"
            #     db.commit()
            #     continue  # Skip post-farewell logic

            db.commit()

        # 💬 Optional followup logic (e.g. for logging exit mood)
        # handle_soft_session_close(s, db)

    db.close()
