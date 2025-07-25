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
from app.services.general_prompts import GLOBAL_USER_PROMPT

async def handle_confirmation(session):
    return await confirm_input_summary(session)

async def handle_confirmed_game(db, user, session):
    game_title = session.last_recommended_game
    if session.meta_data.get("ask_confirmation", False):
        user_prompt = (
            f"{GLOBAL_USER_PROMPT}\n"
            "The user confirmed they liked the last recommended game.\n"
            "Ask in a warm, upbeat, and conversational way what they enjoyed most about it. ask clear question yet different words or phrase with the same meaning.\n"
            "Vary the phrasing each time; never repeat previous wording or use static templates."
            "Keep your question short—just 1 or 2 lines."
            "Return only the new user-facing message."
            "Do not use emoji which is used in previous messages."
        )
        session.meta_data["ask_confirmation"] = False
        db.commit()
        return user_prompt
    else:
        user_prompt = f"""
        {GLOBAL_USER_PROMPT}

        ---

        You are Thrum — a tone-matching, emotionally intelligent game companion who speaks like a close friend.

        The user just accepted the game: **{game_title}**  
        This is your moment to celebrate this trust — in a real, warm, casual way, like how would friends react if someone responses positive on a suggestion.

        → Write one short message (1–2 lines max) that:
        - Mirrors the user's tone (e.g., hype, chill, sarcastic, quiet)
        - Feels like a friend texting back after sharing something cool, and wants to make sure the other is heard (draper style) and get them emotionally attached since this was a success.
        - Has no hardcoded phrasing
        - Never uses robotic lines like "thanks for accepting" or "hope you enjoy"

        Optional: you can hint that you'll check back later, but only if it feels natural, how friends would do this over whatsapp, but always ask if the user would appreciate that.

        ⚠️ DO NOT write a flat thank you or generic sign-off. Keep it alive and connected.

        """.strip()
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
            delay = timedelta(seconds=15)
            # Check if the delay time has passed since the last interaction
            print(f"Checking if we need to ask for name for user {user.phone_number} in session {s.session_id} ::  dont_give_name  {s.meta_data['dont_give_name']}")
            if now - s.last_thrum_timestamp > delay:
                # Ensure the session meta_data flag is set to avoid re-asking the name
                s.meta_data["dont_give_name"] = True
                db.commit()
                print(f"Session {s.session_id} :: Asking for name for user {user.phone_number} :: dont_give_name  {s.meta_data['dont_give_name']}")
                user_interactions = [i for i in s.interactions if i.sender == SenderEnum.User]
                last_user_reply = user_interactions[-1].content if user_interactions else ""
                
                # Ask for the user's name
                response_prompt = (
                    "Generate a polite, natural message (max 10–12 words) asking the user for their name.\n"
                    "The tone should be friendly and casual, without being too formal or overly casual.\n"
                    "Ensure it doesn’t feel forced, just a simple request to know their name.\n"
                    "Output only the question, no extra explanations or examples."
                    "Do not use emoji. Ask like Thrum wants to remember for next time."
                )
                
                reply = await format_reply(session=s, user_input=last_user_reply, user_prompt=response_prompt)
                await send_whatsapp_message(user.phone_number, reply)

    db.close()  # Close the DB session