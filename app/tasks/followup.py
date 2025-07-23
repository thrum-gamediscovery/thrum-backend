# app/tasks/followup.py
from celery import shared_task
from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.db.models import Interaction, Session
from app.db.models.enums import ResponseTypeEnum, PhaseEnum
import json
import os
from app.utils.whatsapp import send_whatsapp_message
from app.services.tone_classifier import classify_tone  
from app.services.input_classifier import analyze_followup_feedback  
from app.services.thrum_router.phase_ending import handle_ending
from app.services.share_intent import is_share_intent
import random

@shared_task
async def send_feedback_followups():
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=30)

        interactions = db.query(Interaction).join(Session).filter(
            Interaction.response_type == ResponseTypeEnum.GameRec,
            Interaction.timestamp < cutoff,
            Session.user_feedback == None
        ).all()

        for interaction in interactions:
            user = interaction.session.user
            game = interaction.game

            if user and user.phone_number:
                send_feedback_followup_message(
                    user_phone=user.phone_number.replace("whatsapp:", ""),
                    message=f"👋 Hey! Did you get a chance to try *{game.name if game else 'the game'}*? Let me know 👍 or 👎!"
                )
    finally:
        db.close()

async def handle_followup_logic(db, session, user, user_input, classification):
    from app.services.thrum_router.phase_discovery import handle_discovery
    feedback = await analyze_followup_feedback(user_input, session)

    print(feedback)
    parsed = json.loads(feedback)
    intent = parsed.get("intent")
    
    # Set game_interest_confirmed flag when user shows interest in a game
    if intent in ["game_accepted"]:
        session.meta_data = session.meta_data or {}
        session.meta_data["game_interest_confirmed"] = True
        db.commit()
    
    # Set game_interest_confirmed flag if the intent indicates interest in the game
    if intent in ["game_accepted", "game_interest_confirmed"]:
        session.meta_data = session.meta_data or {}
        session.meta_data["game_interest_confirmed"] = True
        db.commit()

    # Check if user has accepted a game recommendation
    game_accepted = False
    last_game_title = None
    if session.game_recommendations:
        last_rec = session.game_recommendations[-1]
        if last_rec.accepted is True:
            game_accepted = True
            last_game_title = last_rec.game.title if last_rec.game else "the game"

    # 👥 Share intent detected
    if await is_share_intent(user_input):
        return "Send this to your friends: 'I just got a perfect game drop from Thrum 🎮 — it's a vibe! Tap here to try it 👉 https://wa.me/12764000071?text=Hey%2C%20I%20heard%20Thrum%20can%20drop%20perfect%20games%20for%20my%20mood.%20Hit%20me%20with%20one!%20🔥'"

    # If user accepted a game, don't immediately suggest another one
    if game_accepted and intent in ["dont_want_another", "game_accepted"]:
        # Set a timestamp for when the game was accepted
        session.meta_data = session.meta_data or {}
        session.meta_data["game_accepted_at"] = datetime.utcnow().isoformat()
        session.meta_data["accepted_game_title"] = last_game_title
        db.commit()
        
        # Thank the user and end the conversation naturally
        return f"Awesome, enjoy {last_game_title}! I'll check back with you later to see how it went."

    if intent in ["want_another"]:
        session.phase = PhaseEnum.DISCOVERY
        return await handle_discovery(db=db, session=session, user=user)

    if intent in ["dont_want_another"]:
        if not user.playtime:
            playtime_prompts = [
                f"When do you usually play, {user.name}? Evenings, weekends, or those late-night sessions?",
                f"{user.name}, what’s your usual game time — after dinner, late at night, or whenever you’re free?",
                f"{user.name}, are you more of a weekend gamer or a midnight kind of player?",
                f"When does gaming usually happen for you, {user.name}? Evenings or those 2AM marathons?",
                f"{user.name}, do you sneak in your games at night, on lazy Sundays, or some other time?",
                f"Evenings, weekends, or late nights — when’s your favorite time to play, {user.name}?"
            ]
            reply = random.choice(playtime_prompts)
            print(f"handle_followup_logic : {reply}")
            return reply
        
    session.phase = PhaseEnum.ENDING
    return await handle_ending(session)

            # followup_prompts = [
            #     "Cool — just wondering, do you lean more toward story-rich games or fast-action ones?",
            #     "One last thing — do you usually enjoy emotional stories or chaos and action?",
            #     "Quick vibe check: you prefer deep stories or quick, intense gameplay?",
            #     "Just curious — story-driven vibes or pure arcade-style action?",
            #     "Do you tend to dive into game stories, or go straight for the action?",
            #     "Final thing — do stories hook you, or are you here for gameplay?"
            # ]
            # reply = random.choice(followup_prompts)
            # print(f"handle_followup_logic : {reply}")
            # session.awaiting_reply = True
            # return reply

            
async def get_post_recommendation_reply(user_input: str, last_game_name: str, session: Session, db) -> str | None:
    """
    Detect if the user is reacting to a game we just recommended.
    Log reaction and return soft follow-up.
    """
    tone = await classify_tone(user_input)
    reply = None

    if tone == "cold":
        reply = f"Too off with *{last_game_name}*? Want me to change it up?"
    elif tone == "positive":
        # Mark the game as accepted in the session
        if session.game_recommendations:
            last_rec = session.game_recommendations[-1]
            if last_rec.game and last_rec.game.title == last_game_name:
                last_rec.accepted = True
                db.commit()
                
        # Store acceptance info in session metadata
        session.meta_data = session.meta_data or {}
        session.meta_data["game_accepted_at"] = datetime.utcnow().isoformat()
        session.meta_data["accepted_game_title"] = last_game_name
        db.commit()
        
        # Thank the user instead of asking if they want to go deeper
        reply = f"Awesome, enjoy *{last_game_name}*! I'll check back with you later to see how it went."
    elif tone == "vague":
        reply = f"Not sure if *{last_game_name}* hit right? I can keep digging if you want."

    if tone:
        # 📝 Log tone reaction
        meta = session.meta_data or {}
        history = meta.get("reaction_history", [])
        history.append({
            "game": last_game_name,
            "tone": tone,
            "timestamp": datetime.utcnow().isoformat()
        })

        # 🧠 Detect shift if 2+ cold/vague in last 3
        recent = [h["tone"] for h in history[-3:]]
        shift = recent.count("cold") + recent.count("vague") >= 2
        meta["reaction_history"] = history
        meta["user_preference_shift"] = shift
        session.meta_data = meta
        db.commit()

    return reply

# New function to check for delayed follow-ups
@shared_task
async def check_delayed_followups():
    """
    Checks for sessions with accepted games that need a delayed follow-up
    """
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        
        # Find sessions with accepted games
        sessions = db.query(Session).filter(
            Session.meta_data.has_key("game_accepted_at")
        ).all()
        
        for session in sessions:
            # Skip if we've already sent a delayed follow-up
            if session.meta_data.get("delayed_followup_sent"):
                continue
                
            # Parse the acceptance timestamp
            try:
                accepted_at = datetime.fromisoformat(session.meta_data["game_accepted_at"])
                # Check if it's been at least 3 hours
                if now - accepted_at >= timedelta(hours=3):
                    user = session.user
                    game_title = session.meta_data.get("accepted_game_title", "the game")
                    
                    # Generate dynamic follow-up message using OpenAI
                    from app.services.session_memory import SessionMemory
                    from app.services.tone_engine import get_last_user_tone_from_session
                    import openai
                    
                    session_memory = SessionMemory(session)
                    memory_context_str = session_memory.to_prompt()
                    last_user_tone = get_last_user_tone_from_session(session)
                    
                    prompt = f"""
                    USER MEMORY & RECENT CHAT:
                    {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}

                    You are Thrum — an emotionally aware, tone-matching gaming companion.

                    The user accepted your recommendation for {game_title} about 3 hours ago.
                    Write ONE short, natural follow-up to check if they had a chance to try the game and how they liked it.
                    If they haven't played it yet, ask if they'd like a different recommendation.

                    Your response must:
                    - Reflect the user's tone: {last_user_tone} (e.g., chill, genz, hype, unsure, etc.)
                    - Use fresh and varied phrasing every time — never repeat past follow-up styles
                    - Be no more than 25 words. If you reach 25 words, stop immediately.
                    - Specifically ask about their experience with {game_title}
                    - Include a question about whether they want something different if they haven't played
                    - Avoid any fixed templates or repeated phrasing

                    Tone must feel warm, casual, playful, or witty — depending on the user's tone.

                    Only output one emotionally intelligent follow-up. Nothing else.
                    """
                    
                    client = openai.AsyncOpenAI()
                    response = await client.chat.completions.create(
                        model=os.getenv("GPT_MODEL"),
                        temperature=0.7,
                        messages=[{"role": "user", "content": prompt.strip()}]
                    )
                    message = response.choices[0].message.content.strip()
                    
                    await send_whatsapp_message(user.phone_number, message)
                    
                    # Mark that we've sent the follow-up
                    session.meta_data["delayed_followup_sent"] = True
                    session.meta_data["delayed_followup_sent_at"] = now.isoformat()
                    db.commit()
            except (ValueError, TypeError, KeyError):
                continue
    finally:
        db.close()

FAREWELL_LINES = [
    "Ghost mode? Cool, I’ll be here later 👻",
    "No pressure — ping me when you're ready for more 🎮",
    "Alrighty, I’ll vanish till you need me 😄",
    "Catch you later! Got plenty more when you’re in the mood 🕹️"
]

async def handle_soft_session_close(session, db):
    from app.services.session_manager import is_session_idle_or_fading

    if not is_session_idle_or_fading(session):
        return

    user = session.user
    if session.meta_data.get("session_closed"):
        return

    session.meta_data["closed_at"] = datetime.utcnow().isoformat()
    session.meta_data["session_closed"] = True
    session.exit_mood = session.exit_mood or user.mood_tags.get(datetime.utcnow().date().isoformat())

    farewell = random.choice(FAREWELL_LINES)
    await send_whatsapp_message(user.phone_number, farewell)
    db.commit()