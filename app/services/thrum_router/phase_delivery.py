from app.services.game_recommend import game_recommendation
from app.services.session_memory import format_game_output
from app.db.models.enums import PhaseEnum
from app.db.models.session import Session  
from sqlalchemy.orm import Session as DBSession  
from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.utils.whatsapp import send_whatsapp_message

async def handle_delivery(db: DBSession, session, user):
    game, _ = await game_recommendation(db=db, user=user, session=session)
    if game:
        session.last_recommended_game = game["title"]
        session.phase = PhaseEnum.FOLLOWUP
        session.followup_triggered = True
    else:
        return "not game"
    # Optional: build user_context from session
    user_context = {
        "mood": session.exit_mood,
        "genre": getattr(session, "genre", None),
        "platform": session.platform_preference
    }
    return await format_game_output(game,user_context)

async def recommend_game():
    db = SessionLocal()
    now = datetime.utcnow()

    sessions = db.query(Session).filter(
        Session.awaiting_reply == True,
        Session.intent_override_triggered == True
    ).all()
    for s in sessions:
        user = s.user
        if not s.last_thrum_timestamp:
            continue

        delay = timedelta(seconds=10)

        if now - s.last_thrum_timestamp > delay:
            reply = await handle_delivery(db=db, session=s, user=user)
            await send_whatsapp_message(user.phone_number, reply)
            s.phase = PhaseEnum.FOLLOWUP
            # 🧠 Track nudge + potential coldness
            s.last_thrum_timestamp = now
            s.intent_override_triggered = False
        db.commit()
    db.close()
