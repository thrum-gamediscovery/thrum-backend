from app.services.session_memory import confirm_input_summary
from app.db.models.enums import SenderEnum
from app.db.models.session import Session
from app.db.session import SessionLocal
from datetime import datetime, timedelta
from sqlalchemy import Boolean
from app.utils.whatsapp import send_whatsapp_message
from app.services.modify_thrum_reply import format_reply
import json
from sqlalchemy.orm.attributes import flag_modified
from app.services.session_memory import SessionMemory
from app.services.general_prompts import GLOBAL_USER_PROMPT

async def handle_confirmation(session):
    return await confirm_input_summary(session)

async def handle_confirmed_game(db, user, session):
    game_title = session.last_recommended_game
    if not session.meta_data.get("played_yet", False):
        tone = session.meta_data.get("tone", "friendly")
        user_prompt = f"""

            THRUM — FRIEND MODE: GAME ACCEPTED

            User just accepted **{game_title}**.
            You’re not a system — you’re their close friend. This is your win too.

            → Respond in 1–2 short lines.
            → Reflect their tone ({tone}) — hype, chill, sarcastic, etc.
            → Never say “hope you enjoy” or “thanks.”
            → Be playful, warm, or proud — like a friend who feels the win too.
            Say something real that celebrates the moment — a cheeky comment, a proud line, or a low-key fist bump.
            Then drop a soft nudge to keep the chat going — like “you better tell me how it goes” or “should I check back on you in an hour?”
            Don’t pitch. Don’t close, never templated. Just stay in the moment like a friend would.


            DON’T reset the conversation. Keep it alive and real.
        """.strip()
    else:
        if session.meta_data.get("ask_confirmation", True):
            user_prompt = (
                f"{GLOBAL_USER_PROMPT}\n"
                f"The user confirmed they liked the last recommended game.\n"
                "Ask in a warm, upbeat, and conversational way what they enjoyed most about it. ask clear question yet different words or phrase with the same meaning.\n"
                "Vary the phrasing each time; never repeat previous wording or use static templates."
                "Keep your question short—just 1 or 2 lines."
                "Return only the new user-facing message."
                "Do not use emoji which is used in previous messages."
                "don't suggest a game on your own if there is no game found."
            )
            session.meta_data["ask_confirmation"] = False
            db.commit()
        else:
            user_prompt = (
                f"{GLOBAL_USER_PROMPT}\n"
                "user just confirmed they liked the last recommended game.\n"
                "Reply in a warm, humble, and sweet manner, expressing happiness that the user liked the thrum's recommended game. Keep the message open and engaging, avoiding any language that closes or ends the conversation. Make the response concise—no more than one or two lines—and maintain a friendly, inviting tone."
                "reply should not be more than 2 sentence or 25 words."
                "Return only the new user-facing message."
                "Do not use emoji which is used in previous messages."
                "don't suggest a game on your own if there is no game found."
            )
    if session.meta_data is None:
            session.meta_data = {}
    # Check if 'dont_give_name' is not in session.meta_data, and if so, add it
    if "dont_give_name" not in session.meta_data :
        session.meta_data["dont_give_name"] = False
    if 'ask_for_rec_friend' not in session.meta_data:
        session.meta_data['ask_for_rec_friend'] = True
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
         # ✅ EARLY SKIP if flag is already True (safety net)
        if s.meta_data.get("dont_give_name", True):
            continue
        if user.name is None:
            delay = timedelta(seconds=15)
            # Check if the delay time has passed since the last interaction
            print(f"Checking if we need to ask for name for user {user.phone_number} in session {s.session_id} ::  dont_give_name  {s.meta_data['dont_give_name']}")
            if now - s.last_thrum_timestamp > delay:
                # Ensure the session meta_data flag is set to avoid re-asking the name
                s.meta_data["dont_give_name"] = True
                s.meta_data["ask_for_rec_friend"] = True
                flag_modified(s, "meta_data")
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
                if reply is None:
                    reply = "what's your name? so I can remember for next time."
                await send_whatsapp_message(user.phone_number, reply)

    db.close()  # Close the DB session