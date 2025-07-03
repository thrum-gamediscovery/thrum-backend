from app.tasks.followup import handle_followup_logic
from app.db.models.enums import PhaseEnum
from app.db.models.session import Session
from datetime import datetime, timedelta
from app.db.session import SessionLocal
import openai
import os
from app.utils.whatsapp import send_whatsapp_message

openai.api_key = os.getenv("OPENAI_API_KEY")

async def handle_followup(db, session, user, user_input):
    return await handle_followup_logic(db=db, session=session, user=user, user_input=user_input)

async def ask_feedback(session) -> str:
    game_title = session.last_recommended_game or "that game"
    prompt = f"""
You're Thrum — a fast, friendly, emotionally smart game recommender.
The user just got a game suggestion: "{game_title}"
Now, ask them *one* natural, human-sounding question that combines:
- Asking if they liked the game
- OR if they want a different one
Use a warm, casual tone. Emojis are not allowed.
Avoid robotic or generic phrasing.
Don’t say the game name again. Just ask a single fun, friendly question.
Return only the question.
"""
    response = await openai.ChatCompletion.acreate(
        model="gpt-4.1-mini",
        temperature=0.5,
        messages=[
            {"role": "user", "content": prompt.strip()}
        ]
    )
    return response.choices[0].message.content.strip()

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

        delay = timedelta(seconds=5)

        if now - s.last_thrum_timestamp > delay:
            reply = await ask_feedback(s)
            await send_whatsapp_message(user.phone_number, reply)
            s.last_thrum_timestamp = now
            s.awaiting_reply = True
            s.followup_triggered = False
        db.commit()
    db.close()