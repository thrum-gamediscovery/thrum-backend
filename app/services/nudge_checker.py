"""
📄 File: app/services/nudge_checker.py
Checks sessions for inactivity after Thrum speaks and sends a gentle nudge.
"""

from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.db.models.session import Session
from app.services.session_manager import close_session
from app.utils.whatsapp import send_whatsapp_message
import random

NUDGE_LINES = [
    "Still there? 👀",
    "Want another rec? 🎮",
    "Can I throw you a wild card pick?",
    "No rush - just poke me when ready 😄"
]

FAREWELL_LINES = [
    "Ghost mode? Cool, I'll be here later.",
    "Ping me when you want more hits.",
    "Catch you on the flip side.",
    "I'm out for now - holler when you're back."
]

def choose_nudge():
    return random.choice(NUDGE_LINES)

def choose_farewell():
    return random.choice(FAREWELL_LINES)

def check_for_nudge():
    db = SessionLocal()
    now = datetime.utcnow()

    sessions = db.query(Session).filter(
        Session.awaiting_reply == True,
        Session.state.in_(["ACTIVE", "ONBOARDING"])  # only nudge active/onboarding
    ).all()

    for s in sessions:
        user = s.user
        if not s.last_thrum_timestamp:
            continue

        silence_count = user.silence_count or 0
        silence_duration = now - s.last_thrum_timestamp

        # ❌ Close session softly if too long silence and ignored 3 nudges
        if silence_count >= 3 and silence_duration > timedelta(minutes=5):
            farewell = choose_farewell()
            send_whatsapp_message(user.phone_number, farewell)
            close_session(db, session=s, reason="idle", mood=None)
            continue  # Skip nudging

        # 🟡 Otherwise, gently nudge
        delay = timedelta(seconds=30 if silence_count > 2 else 60)
        if silence_duration > delay:
            nudge = choose_nudge()
            send_whatsapp_message(user.phone_number, nudge)
            s.awaiting_reply = False
            user.silence_count = silence_count + 1
            db.commit()

    db.close()