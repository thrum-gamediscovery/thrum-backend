from app.services.session_memory import confirm_input_summary
from app.db.models.enums import SenderEnum
from app.db.models.session import Session
from app.db.session import SessionLocal
from datetime import datetime, timedelta
from sqlalchemy import Boolean
from app.utils.whatsapp import send_whatsapp_message
from app.services.modify_thrum_reply import format_reply
import json

async def handle_confirmation(session):
    return await confirm_input_summary(session)

async def handle_confirmed_game(db, user, session):
    user_prompt = (
        "The user confirmed they liked the last recommended game.\n"
        "Use their input, your last reply, and the game title to reflect emotionally.\n"
        "Reply with a short, natural confirmation — no more than 10 words.\n"
        "Make it warm, upbeat, or playful — never robotic or generic.\n"
        "Do not suggest another game yet. Just acknowledge the moment with joy or connection."
    )
    
    if session.meta_data is None:
            session.meta_data = {}
    # Check if 'dont_give_name' is not in session.meta_data, and if so, add it
    if "dont_give_name" not in session.meta_data:
        session.meta_data["dont_give_name"] = False
    
    db.commit()
    return user_prompt

async def ask_for_name_if_needed(session):
    db = SessionLocal()
    now = datetime.utcnow()

    sessions = db.query(Session).filter(
        Session.last_thrum_timestamp.isnot(None),
        Session.user.hasattr("name"),
        Session.user.name == None,
        Session.meta_data["dont_give_name"].astext.cast(Boolean) == False
    ).all()

    for s in sessions:
        user = s.user
        if user.name is None:
            delay = timedelta(seconds=5)

            if now - s.last_thrum_timestamp > delay:
                user_interactions = [i for i in s.interactions if i.sender == SenderEnum.User]
                last_user_reply = user_interactions[-1].content if user_interactions else ""
                print(f"User's name is missing. Asking for the user's name.")
                response_prompt = f"""
                ask name
                """
                reply = await format_reply(session=session,user_input=last_user_reply, user_prompt=response_prompt)
                await send_whatsapp_message(user.phone_number, reply)

   