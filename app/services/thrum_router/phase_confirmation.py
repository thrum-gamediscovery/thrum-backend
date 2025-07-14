from app.services.session_memory import confirm_input_summary
from app.db.models.enums import SenderEnum
from app.db.models.session import Session
from app.db.session import SessionLocal
from datetime import datetime, timedelta
from sqlalchemy import Boolean
from app.utils.whatsapp import send_whatsapp_message
from app.services.modify_thrum_reply import format_reply
import json
from app.services.session_memory import SessionMemory

async def handle_confirmation(session):
    return await confirm_input_summary(session)

async def handle_confirmed_game(db, user, session):
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()

    user_prompt = (
        f"USER MEMORY & RECENT CHAT:\n"
        f"{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}\n\n"
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

async def ask_for_name_if_needed():
    db = SessionLocal()
    now = datetime.utcnow()

    sessions = db.query(Session).join(Session.user).filter(
        Session.last_thrum_timestamp.isnot(None),
        Session.meta_data["dont_give_name"].astext.cast(Boolean) == False
    ).all()

    for s in sessions:
        user = s.user
        if user.name is None:
            delay = timedelta(seconds=10)

            if now - s.last_thrum_timestamp > delay:
                user_interactions = [i for i in s.interactions if i.sender == SenderEnum.User]
                last_user_reply = user_interactions[-1].content if user_interactions else ""
                print(f"User's name is missing. Asking for the user's name.")
                session_memory = SessionMemory(s)
                memory_context_str = session_memory.to_prompt()

                response_prompt  = (
                        f"USER MEMORY & RECENT CHAT:\n"
                        f"{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}\n\n"
                        "Generate a polite, natural message (max 10–12 words) asking the user for their name.\n"
                        "The tone should be friendly and casual, without being too formal or overly casual.\n"
                        "Ensure it doesn’t feel forced, just a simple request to know their name.\n"
                        "Output only the question, no extra explanations or examples."
                        "do not use emoji. and use only one question to ask name."
                    )
                s.meta_data["dont_give_name"] = True
                db.commit()
                reply = await format_reply(session=s, user_input=last_user_reply, user_prompt=response_prompt)
                await send_whatsapp_message(user.phone_number, reply)

    db.close()  # Close the DB session