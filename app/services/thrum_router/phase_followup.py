from app.tasks.followup import handle_followup_logic
from app.db.models.enums import PhaseEnum
from app.db.models.session import Session
from datetime import datetime, timedelta
from app.db.session import SessionLocal
import openai
import os
from app.utils.whatsapp import send_whatsapp_message
import random

openai.api_key = os.getenv("OPENAI_API_KEY")

async def handle_followup(db, session, user, user_input):
    return await handle_followup_logic(db=db, session=session, user=user, user_input=user_input)

async def ask_followup_que(session) -> str:
    if session.story_preference is None:
        last_game = session.game_recommendations[-1].game if session.game_recommendations else None
        if last_game and last_game.has_story is True:
            story_rich_prompts = [
                "That one's a story-rich game. Do you usually enjoy story-driven titles or prefer pure gameplay?",
                "This pick has a strong story focus. Are you into story games or do you like games with less narrative?",
                "It's a story-heavy game. Do you enjoy games where story matters or ones focused on gameplay only?",                    "This one leans into story a lot. Are you a fan of story in games, or do you prefer action-first?",
                "That's a solid story-based experience. Do you usually go for games with story or ones that skip it?",
                "Definitely a story-rich title. Do you like games with deep stories, or more pure gameplay?"
            ]
            return random.choice(story_rich_prompts)

        elif last_game and last_game.has_story is False:
            gameplay_focused_prompts = [
                "This one doesn't have much story. Do you usually prefer gameplay-focused games or story-rich ones?",                    "Not much story here — it's all about the action. Do you like that or something with more story?",
                "It's a gameplay-first game, light on story. Are you more into story-driven games or fast gameplay?",
                "This one skips the story for fast action. Do you enjoy that or do you look for story in your games?",
                "No strong story in this one. Do you prefer story games or are you good with just gameplay?",
                "Very little story here. Are you more into story-rich games or gameplay-heavy ones?"
            ]
            return random.choice(gameplay_focused_prompts)

    else:
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
            reply = await ask_followup_que(s)
            await send_whatsapp_message(user.phone_number, reply)
            s.last_thrum_timestamp = now
            s.awaiting_reply = True
            s.followup_triggered = False
        db.commit()
    db.close()