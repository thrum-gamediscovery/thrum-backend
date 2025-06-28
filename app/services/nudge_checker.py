"""
📄 File: app/services/nudge_checker.py
Checks sessions for inactivity after Thrum speaks and sends a gentle nudge.
"""

from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.db.models.session import Session
from app.utils.whatsapp import send_whatsapp_message
import random
def check_for_nudge():
    db = SessionLocal()
    now = datetime.utcnow()
    sessions = db.query(Session).filter(Session.awaiting_reply == True).all()
    for s in sessions:
        user = s.user
        if not s.last_thrum_timestamp:
            continue
        # :stopwatch: Adaptive nudge delay
        delay = timedelta(seconds=30 if (user.silence_count or 0) > 2 else 60)
        if now - s.last_thrum_timestamp > delay:
            # :dart: Soft nudge
            nudge = random.choice([
                "Still there? 👀",
                "Want another rec? 🎮",
                "Can I throw you a wild card pick?",
                "No rush — just poke me when ready 😄"
            ])
            send_whatsapp_message(user.phone_number, nudge)
            # :white_tick: Track that user was nudged
            s.awaiting_reply = False
            user.silence_count = (user.silence_count or 0) + 1
            db.commit()
    db.close()