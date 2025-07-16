from app.services.game_recommend import game_recommendation
from app.services.input_classifier import have_to_recommend
from app.services.session_memory import format_game_output
from app.db.models.enums import PhaseEnum, SenderEnum
from app.db.models.session import Session  
from sqlalchemy.orm import Session as DBSession  
from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.utils.whatsapp import send_whatsapp_message
import openai
from app.services.session_memory import SessionMemory
from app.services.modify_thrum_reply import format_reply
from app.services.central_system_prompt import NO_GAMES_PROMPT

async def get_recommend(db, user, session):
    game, _ = await game_recommendation(db=db, session=session, user=user)
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()
    platform_link = None
    description=None
    if not game:
        user_prompt = f"""
            USER MEMORY & RECENT CHAT:
            {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}
            {NO_GAMES_PROMPT}
            """ 

        return user_prompt
        # Pull platform info
    preferred_platforms = session.platform_preference or []
    user_platform = preferred_platforms[-1] if preferred_platforms else None
    game_platforms = game.get("platforms", [])
    platform_link = game.get("link", None)
    description = game.get("description",None)
    # Dynamic platform line (not templated)
    if user_platform and user_platform in game_platforms:
        platform_note = f"It’s available on your preferred platform: {user_platform}."
    elif user_platform:
        available = ", ".join(game_platforms)
        platform_note = (
            f"It’s not on your usual platform ({user_platform}), "
            f"but is available on: {available}."
        )
    else:
        platform_note = f"Available on: {', '.join(game_platforms)}."
        # :brain: User Prompt (fresh rec after rejection, warm tone, 20–25 words)
    user_prompt = (
        f"USER MEMORY & RECENT CHAT:\n"
        f"{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}\n\n"
        f"{'platform link: ' + platform_link if platform_link else ''}"
        "The user just rejected the last recommended game.\n"
        "Acknowledge their feedback warmly — let them feel noticed. Never use the same apology or compensation message every time. Avoid 'sorry that didn't click' as a fallback.\n"
        "→ Mention the new game by name — naturally (**{game['title']}**).\n"
        f"→ Give a mini-review based on description:{description} in 3–4 vivid, conversational sentences: quick summary, what’s it about, vibe, mechanic, art, feel, or weirdness.\n"
        "→ Explain *why* this game fits — e.g. 'I thought of this when you said [X]'.\n"
        "→ Use casual, friend-style language: 'This one hits the mood you dropped', 'It’s kinda wild, but I think you’ll like it.'\n"
        f"→ Include a platform mention naturally (make it interesting, not robotic): {platform_note}\n"
        f"platform link :{platform_link}"
        f"If platform_link is not None, then it must be naturally included, do not use brackets or Markdown formatting—always mention the plain URL naturally within the sentence(not like in brackets or like [here],not robotically or bot like) link: {platform_link}\n"
        "Reflect the user's preferences (from user_context), but do NOT repeat the previous tone or any scripted language.\n"
        "Do not mention the last rejected game. No 'maybe'. Use warm, fresh energy.\n"
        "Your reply must be max 25–30 words, sound emotionally alive, and show that you genuinely listened."
    )

    return user_prompt

async def explain_last_game_match(session):
    """
    This function generates a personalized response explaining how the last recommended game matches the user's preferences.
    """
    last_game_obj = session.game_recommendations[-1].game if session.game_recommendations else None
    if last_game_obj is not None:
        last_game = {
            "title": last_game_obj.title,
            "description": last_game_obj.description[:200] if last_game_obj.description else None,
            "genre": last_game_obj.genre,
            "game_vibes": last_game_obj.game_vibes,
            "mechanics": last_game_obj.mechanics,
            "visual_style": last_game_obj.visual_style,
            "has_story": last_game_obj.has_story,
            "available_in_platforms":[platform.platform for platform in last_game_obj.platforms]
        }
    else:
        last_game = None
    
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()
    
    # Generate the user prompt with information about the user's feedback
    user_prompt = f"""USER MEMORY & RECENT CHAT:
    {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}
    Last suggested game: "{last_game.get('title') if last_game else 'None'}"

    Write Thrum’s reply:
    - Describe the last suggested game shortly based on user's last input.
    - Match the user's tone and mood.
    - Do not add name in reply.
    Keep it under 25 words. Add 2–3 emojis that match the tone.
    """
    
    return user_prompt

async def handle_delivery(db: DBSession, session, user, classification, user_input):
    """
    This function handles whether to recommend a new game or explain the last recommended game based on user feedback.
    """
    # Check if a new recommendation is needed based on user preferences and classification
    should_recommend = await have_to_recommend(db=db, user=user, classification=classification, session=session)

    if should_recommend:
        # If a new recommendation is needed, get the recommendation
        recommendation_response = await get_recommend(user=user, db=db, session=session)
        return recommendation_response  # Return the new recommendation
    else:
        # If no new recommendation is needed, explain the last recommended game based on user feedback
        explanation_response = await explain_last_game_match(session=session)
        return explanation_response  # Return the explanation of the last game

async def recommend_game():
    db = SessionLocal()
    now = datetime.utcnow()

    sessions = db.query(Session).filter(
        Session.awaiting_reply == True,
        Session.intent_override_triggered == True
    ).all()
    
    for s in sessions:
        user = s.user
        if not s.last_thrum_timestamp:
            continue
        delay = timedelta(seconds=3)
        if now - s.last_thrum_timestamp > delay:
            s.intent_override_triggered = False
            db.commit()
            user_prompt = await get_recommend(db=db, session=s, user=user)
            user_interactions = [i for i in s.interactions if i.sender == SenderEnum.User]
            user_input = user_interactions[-1].content if user_interactions else ""
            reply = await format_reply(session=s, user_input=user_input, user_prompt=user_prompt)
            await send_whatsapp_message(user.phone_number, reply)
            s.phase = PhaseEnum.FOLLOWUP
            # :brain: Track nudge + potential coldness
            s.last_thrum_timestamp = now
        db.commit()
    db.close()
