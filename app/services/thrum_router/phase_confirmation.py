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

        You are Thrum — a tone-matching, emotionally intelligent game-discovery companion.  

        Now, you must:
        → React like a friend who just nailed a great tip and is excited just like the user.  
        → Match their energy. If they were chill, stay chill. If hyped, be playful. If sarcastic, tease them.  
        → Write one short, emotionally intelligent line that feels like a natural follow-up as how close friends would do.  
        → Celebrate the win in your own way — and gently offer to keep the discovery going.  
        → Do NOT use emojis or robotic phrases like "Great!" or "Recommendation delivered."

        Examples of energy (don't copy-paste):
        - "Knew that would land. Let me know how deep you go with it."
        - "Haha, told you that one would slap."
        - "You're welcome 😏 Now… want me to go even deeper?"

        You must generate **ONE** response in your own words.  

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