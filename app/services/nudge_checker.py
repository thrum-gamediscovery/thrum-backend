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
            # 🎯 Soft nudge message
            # nudge = random.choice([
            #     "Still there? 😊",
            #     "Just drop a word, I’m here.",
            #     "You can say anything — no pressure.",
            #     "Take your time. I’m listening.",
            #     "Feel free to toss in a mood or thought.",
            #     "Whenever you’re ready, just type something.",
            #     "No rush — I’m right here when you are.",
            #     "Say anything — a vibe, a genre, a name.",
            #     "Let’s keep this going when you’re ready!"
            # ])

            prompt = f"""
                You are Thrum, the game discovery buddy.
                Write a short, playful message to gently check if the user is still around after a long pause.
                - Always sound warm and like a real friend.
                - Keep it under 14 words.
                - Never mention inactivity, timeout, or waiting.
                - Vary your reply every time—no repeats or patterns.
                - do not give greeting message.
                - Use the user's name : {user.name} if you know it, but make it natural.
                - No pressure; just a gentle, friendly nudge.
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
