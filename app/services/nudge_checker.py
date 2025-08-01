"""
📄 File: app/services/nudge_checker.py
Checks sessions for inactivity after Thrum speaks and sends a gentle nudge.
Also detects tone-shift (e.g., cold or dry replies).
"""
import os
from openai import AsyncOpenAI
from sqlalchemy import Boolean
from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.db.models.session import Session
from app.db.models.enums import SenderEnum, PhaseEnum
from app.utils.whatsapp import send_whatsapp_message
from app.services.thrum_router.phase_followup import ask_followup_que
from app.services.modify_thrum_reply import format_reply
from sqlalchemy.orm.attributes import flag_modified
from app.services.general_prompts import GLOBAL_USER_PROMPT

model= os.getenv("GPT_MODEL")
client = AsyncOpenAI()

async def check_for_nudge():
    db = SessionLocal()
    now = datetime.utcnow()
    sessions = db.query(Session).filter(Session.awaiting_reply == True, Session.phase != PhaseEnum.ENDING).all()

    for s in sessions:
        user = s.user
        if not s.last_thrum_timestamp:
            continue

        # ⏱️ Adaptive delay based on silence count
        delay = timedelta(seconds=180)

        if now - s.last_thrum_timestamp > delay:
            if user.name:
                user_name = user.name
            else:
                user_name = "unkonwn"

            prompt = f"""
                {GLOBAL_USER_PROMPT}
                -----
                THRUM — NO RESPONSE
                → The user gave minimal feedback — like “cool,” “nice”, “like”,“ok,” “thanks,” or nothing at all. These are low-effort replies that don’t show real engagement.  
                → Your job is to keep the chat alive — casually, without pressure.  
                → You may tease or nudge — in a totally fresh, emotional, generative way. No examples. No recycled phrasing.  
                → Create a moment by offering a light new direction — like a surprising game type or a change in vibe — but always based on what you know about them, based on recent chat history.
                → NEVER ask “do you want another?” or “should I try again?”  
                → NEVER repeat any phrasing, emoji, or fallback line from earlier chats.  
                → Let this feel like natural conversation drift — like two friends texting, one goes quiet, and the other drops a playful line or two to keep it going.  
                - Never suggest a new game on your own if there is no game found
                🌟 Goal: Reopen the door without sounding robotic. Be warm, real, and emotionally alert — like someone who cares about the moment to open the door to a new game discovery.
            """
            
            response = await client.chat.completions.create(
                model=model,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt.strip()}]
            )
            nudge = response.choices[0].message.content.strip()

            await send_whatsapp_message(user.phone_number, nudge)

            # 🧠 Track nudge + potential coldness
            s.awaiting_reply = False
            user.silence_count = (user.silence_count or 0) + 1
            
            db.commit()

    db.close()

async def ask_for_name_if_needed():
    db = SessionLocal()
    now = datetime.utcnow()

    sessions = db.query(Session).join(Session.user).filter(
        Session.last_thrum_timestamp.isnot(None),
        Session.meta_data["dont_give_name"].astext.cast(Boolean) == False
    ).all()

    for s in sessions:
        s = db.query(Session).filter(Session.session_id == s.session_id).one()
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
                db.refresh(s) 
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
                    "→ Never suggest a game on your own if there is no game found"
                )
                
                reply = await format_reply(db=db, session=s, user_input=last_user_reply, user_prompt=response_prompt)
                if reply is None:
                    reply = "what's your name? so I can remember for next time."
                await send_whatsapp_message(user.phone_number, reply)

    db.close()  # Close the DB session

async def get_followup():
    db = SessionLocal()
    now = datetime.utcnow()

    sessions = db.query(Session).filter(
        Session.awaiting_reply == True,
        Session.followup_triggered == True
    ).all()
    for s in sessions:
        user = s.user
        if not s.last_thrum_timestamp:
            continue

        delay = timedelta(seconds=3)
        if now - s.last_thrum_timestamp > delay:
            s.followup_triggered = False
            db.commit()
            reply = await ask_followup_que(s)
            await send_whatsapp_message(user.phone_number, reply)
            s.last_thrum_timestamp = now
            s.awaiting_reply = True
        db.commit()
    db.close()