"""
📄 File: app/services/nudge_checker.py
Checks sessions for inactivity after Thrum speaks and sends a gentle nudge.
Also detects tone-shift (e.g., cold or dry replies).
"""
import os
import random
from openai import AsyncOpenAI
from sqlalchemy import Boolean
from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.db.models.user_profile import UserProfile
from app.db.models.session import Session
from app.db.models.enums import SenderEnum, PhaseEnum
from app.utils.whatsapp import send_whatsapp_message
from app.services.thrum_router.phase_followup import ask_followup_que
from app.services.modify_thrum_reply import format_reply
from sqlalchemy.orm.attributes import flag_modified
from app.services.general_prompts import GLOBAL_USER_PROMPT, NUDGE_CHECKER

model= os.getenv("GPT_MODEL")
client = AsyncOpenAI()

async def check_for_nudge():
    db = SessionLocal()
    now = datetime.utcnow()
    users = db.query(UserProfile).filter(UserProfile.awaiting_reply == True).all()

    for user in users:

        if user.last_thrum_timestamp is None:
            continue

        # ⏱️ Adaptive delay based on silence count
        delay = timedelta(seconds=180)

        if now - user.last_thrum_timestamp > delay:

            choice = random.choice(NUDGE_CHECKER)
            prompt = choice.format(GLOBAL_USER_PROMPT=GLOBAL_USER_PROMPT)
            
            response = await client.chat.completions.create(
                model=model,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt.strip()}]
            )
            nudge = response.choices[0].message.content.strip()

            await send_whatsapp_message(user.phone_number, nudge)

            # 🧠 Track nudge + potential coldness
            user.awaiting_reply = False
            user.silence_count = (user.silence_count or 0) + 1
            
            db.commit()

    db.close()