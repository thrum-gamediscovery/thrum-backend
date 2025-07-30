"""
📄 File: app/services/nudge_checker.py
Checks sessions for inactivity after Thrum speaks and sends a gentle nudge.
Also detects tone-shift (e.g., cold or dry replies).
"""

from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.db.models.session import Session
from app.utils.whatsapp import send_whatsapp_message
from app.db.models.enums import SenderEnum, PhaseEnum
import random
import os
from openai import AsyncOpenAI
from app.services.general_prompts import GLOBAL_USER_PROMPT

model= os.getenv("GPT_MODEL")
client = AsyncOpenAI()

# 🧠 GPT-based tone detection
async def detect_user_is_cold(session, db) -> bool:
    """
    Returns True if the user has been 'cold' (dry, closed, or neutral) in at least 2 of their last 3 messages.
    Uses LLM to classify each message's tone from a fixed set of allowed labels.
    """
    
    user_msgs = [i for i in session.interactions if i.sender == SenderEnum.User][-3:]
    if len(user_msgs) < 2:
        return False

    dry_like_count = 0
    allowed_labels = [
        "chill",
        "chaotic",
        "dry",
        "genz",
        "formal",
        "emotional",
        "closed",
        "neutral"
    ]

    for i in user_msgs:
        prompt = f"""
            Classify the tone of this message into one of the following (respond with only one word from the list, all lowercase):

            [chill, chaotic, dry, genz, formal, emotional, closed, neutral]

            Message: "{i.content}"

            Only use a word from this list. If you’re unsure, pick the closest match.
            Do not add any explanation. Example output: dry
            """
        
        try:
            res = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            label = res["choices"][0]["message"]["content"].strip().lower()

            if label in allowed_labels:
                if label in ["dry", "closed", "neutral"]:
                    dry_like_count += 1
            else:
                # log error, default to neutral, etc.
                label = "neutral"
        except:
            continue

    return dry_like_count >= 2

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
