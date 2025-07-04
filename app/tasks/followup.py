# app/tasks/followup.py
from celery import shared_task
from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.db.models import Interaction, Session
from app.db.models.enums import ResponseTypeEnum, PhaseEnum
import json
from app.utils.whatsapp import send_whatsapp_message
from app.services.tone_classifier import classify_tone  
from app.services.input_classifier import analyze_followup_feedback  
from app.services.thrum_router.phase_ending import handle_ending
from app.services.thrum_router.phase_discovery import handle_discovery
import random

@shared_task
async def send_feedback_followups():
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

async def handle_followup_logic(db, session, user, user_input):
    feedback = await analyze_followup_feedback(user_input, session)
    print(f"feedback : {feedback}")
    parsed = json.loads(feedback)
    intent = parsed.get("intent")

    if intent in ["want_another"]:
        session.phase = PhaseEnum.DISCOVERY
        return await handle_discovery(db=db,session=session, user=user)

    if intent in ["dont_want_another"]:
        if not user.name:
            name_prompts = [
                "BTW, what's your name? I'd love to remember you next time 😊",
                "Can I save your name for next time? Feels like we're already vibing 👀",
                "I'm curious — what should I call you?",
                "Wanna tell me your name? Just so I can keep it in mind for later!",
                "Got a name I can remember you by? Always nice to keep things personal 🙌",
                "What's your name, friend? I've got a good memory when it counts 💾"
            ]

            return random.choice(name_prompts)
        elif not user.playtime:
            playtime_prompts = [
                f"When do you usually play, {user.name}? Evenings, weekends, or those late-night sessions?",
                f"{user.name}, what’s your usual game time — after dinner, late at night, or whenever you’re free?",
                f"{user.name}, are you more of a weekend gamer or a midnight kind of player?",
                f"When does gaming usually happen for you, {user.name}? Evenings or those 2AM marathons?",
                f"{user.name}, do you sneak in your games at night, on lazy Sundays, or some other time?",
                f"Evenings, weekends, or late nights — when’s your favorite time to play, {user.name}?"
            ]

            return random.choice(playtime_prompts)
        else:
            session.phase = PhaseEnum.ENDING
            await handle_ending(session)
async def get_post_recommendation_reply(user_input: str, last_game_name: str, session: Session, db) -> str | None:
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

async def handle_soft_session_close(session, db):
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
    await send_whatsapp_message(user.phone_number, farewell)
    db.commit()