# app/tasks/followup.py
from celery import shared_task
from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.db.models import Interaction, Session
from app.db.models.enums import ResponseTypeEnum
from app.services.send_feedback_message import send_feedback_followup_message
from app.services.tone_shift_detection import detect_tone_shift, mark_session_cold
from app.utils.whatsapp import send_whatsapp_message
from app.services.tone_classifier import classify_tone  # ✅ LLM-powered tone classifier
import random

@shared_task
def send_feedback_followups():
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=30)

        interactions = db.query(Interaction).join(Session).filter(
            Interaction.response_type == ResponseTypeEnum.GameRec,
            Interaction.timestamp < cutoff,
            Session.user_feedback == None
        ).all()

        for interaction in interactions:
            user = interaction.session.user
            game = interaction.game

            if user and user.phone_number:
                send_feedback_followup_message(
                    user_phone=user.phone_number.replace("whatsapp:", ""),
                    message=f"👋 Hey! Did you get a chance to try *{game.name if game else 'the game'}*? Let me know 👍 or 👎!"
                )
    finally:
        db.close()

def handle_followup_logic(session, db):
    """
    Check tone shift and nudge user softly if cold.
    """
    if detect_tone_shift(session):
        print("⚠️ Tone shift detected — user may be disengaging.")
        mark_session_cold(db, session)
        return {
            "message": "Getting some low vibes… wanna switch it up? Or take a break — totally cool.",
            "flag": "cold"
        }

    return {
        "message": None,
        "flag": "normal"
    }

def get_post_recommendation_reply(user_input: str, last_game_name: str, session: Session, db) -> str | None:
    """
    Detect if the user is reacting to a game we just recommended.
    Log reaction and return soft follow-up.
    """
    tone = classify_tone(user_input)
    reply = None

    if tone == "cold":
        reply = f"Too off with *{last_game_name}*? Want me to change it up?"
    elif tone == "positive":
        reply = f"You’re into *{last_game_name}* vibes then? Wanna go deeper or switch it up?"
    elif tone == "vague":
        reply = f"Not sure if *{last_game_name}* hit right? I can keep digging if you want."

    if tone:
        # 📝 Log tone reaction
        meta = session.meta_data or {}
        history = meta.get("reaction_history", [])
        history.append({
            "game": last_game_name,
            "tone": tone,
            "timestamp": datetime.utcnow().isoformat()
        })

        # 🧠 Detect shift if 2+ cold/vague in last 3
        recent = [h["tone"] for h in history[-3:]]
        shift = recent.count("cold") + recent.count("vague") >= 2
        meta["reaction_history"] = history
        meta["user_preference_shift"] = shift
        session.meta_data = meta
        db.commit()

    return reply

FAREWELL_LINES = [
    "Ghost mode? Cool, I’ll be here later 👻",
    "No pressure — ping me when you're ready for more 🎮",
    "Alrighty, I’ll vanish till you need me 😄",
    "Catch you later! Got plenty more when you’re in the mood 🕹️"
]

def handle_soft_session_close(session, db):
    from app.services.session_manager import is_session_idle_or_fading

    if not is_session_idle_or_fading(session):
        return

    user = session.user
    if session.meta_data.get("session_closed"):
        return

    session.meta_data["closed_at"] = datetime.utcnow().isoformat()
    session.meta_data["session_closed"] = True
    session.exit_mood = session.exit_mood or user.mood_tags.get(datetime.utcnow().date().isoformat())

    farewell = random.choice(FAREWELL_LINES)
    send_whatsapp_message(user.phone_number, farewell)
    db.commit()
