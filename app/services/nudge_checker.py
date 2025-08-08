"""
📄 File: app/services/nudge_checker.py
Checks sessions for inactivity after Thrum speaks and sends a gentle nudge.
Also detects tone-shift (e.g., cold or dry replies).
"""
import os
import random
from sqlalchemy import cast, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from openai import AsyncOpenAI
from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.db.models.user_profile import UserProfile
from app.db.models.session import Session
from app.db.models.enums import SenderEnum
from app.utils.whatsapp import send_whatsapp_message
from app.services.modify_thrum_reply import format_reply
from app.services.general_prompts import GLOBAL_USER_PROMPT, NUDGE_CHECKER
from app.services.thrum_router.phase_delivery import get_recommend

model = os.getenv("GPT_MODEL", "gpt-4o")
client = AsyncOpenAI()

async def build_ambiguity_nudge(db, session,user):
    sorted_interactions = sorted(session.interactions, key=lambda i: i.timestamp, reverse=True)
    user_interactions = [i for i in sorted_interactions if i.sender == SenderEnum.User]
    user_input = user_interactions[0].content if user_interactions else ""
    tone = session.meta_data.get("tone","friendly")
    mood = session.exit_mood
    user_prompt = f"""
        User didn’t reply to your clarification question.

        Write a short, friendly nudge — like a friend checking in.  
        Tone: {tone}, Mood: {mood}

        Examples (don’t copy):
        - “Wanna just let me freestyle it?”
        - “Still up for a rec if I guess?”

        Only output 1 sentence.
        """ 
    session.meta_data['clarification_status'] = 'nudge_sent'
    db.commit()
    reply = await format_reply(db=db, session=session, user_input=user_input, user_prompt=user_prompt)
    return reply

async def fallback_rec_ambiguity(db, session,user):
    reply = None
    sorted_interactions = sorted(session.interactions, key=lambda i: i.timestamp, reverse=True)
    user_interactions = [i for i in sorted_interactions if i.sender == SenderEnum.User]
    user_input = user_interactions[0].content if user_interactions else ""
    session.meta_data['clarification_status'] = 'fallback_sent'
    db.commit()
    if session.discovery_questions_asked >=2 and session.game_rejection_count <=2:
        user_prompt = await get_recommend(db=db, session=session,user=user)
        reply = await format_reply(db=db, session=session, user_input=user_input, user_prompt=user_prompt)
    return reply

async def check_for_nudge():
    db = SessionLocal()
    now = datetime.utcnow()
    users = db.query(UserProfile).filter(UserProfile.awaiting_reply == True).all()

    for user in users:
        reply = None
        if user.last_thrum_timestamp is None:
            continue
        
        if now - user.last_thrum_timestamp > timedelta(seconds=180):

            choice = random.choice(NUDGE_CHECKER)
            prompt = choice.format(GLOBAL_USER_PROMPT=GLOBAL_USER_PROMPT)
            
            response = await client.chat.completions.create(
            model=model,
            temperature=0.7,
                messages=[{"role": "user", "content": prompt.strip()}]
            )
            content = response.choices[0].message.content
            reply = content.strip() if content else None

            # 🧠 Track nudge + potential coldness
            user.awaiting_reply = False
            user.silence_count = (user.silence_count or 0) + 1
                
            db.commit()

        session = (
            db.query(Session)
            .filter(
                Session.user_id == user.user_id,
                Session.meta_data['ambiguity_clarification'].astext == 'true'
            )
            .order_by(Session.end_time.desc())
            .first()
        )
        if session :
            if session.meta_data.get('ambiguity_clarification', False):
                if 'clarification_status' in session.meta_data and now - user.last_thrum_timestamp > timedelta(seconds=25):
                    if session.meta_data.get('clarification_status',None) == 'waiting' and now - user.last_thrum_timestamp > timedelta(seconds=45):
                        reply = await build_ambiguity_nudge(db=db,session=session,user=user)
                    elif session.meta_data.get('clarification_status',None) == 'nudge_sent' and now - user.last_thrum_timestamp > timedelta(seconds=75):
                        reply = await fallback_rec_ambiguity(db=db,session=session,user=user)

                # ⏱️ Adaptive delay based on silence count
        if reply is not None:
            await send_whatsapp_message(user.phone_number, reply)
            
    db.close()