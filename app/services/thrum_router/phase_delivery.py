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
    print(f"Game recommendation: {game}")
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()
    platform_link = None
    last_session_game = None
    description=None
    mood = session.exit_mood  or "neutral"
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
    is_last_session_game = game.get("last_session_game",{}).get("is_last_session_game") 
    if is_last_session_game:
        last_session_game = game.get("last_session_game", {}).get("title")
    user_prompt = (
        f"USER MEMORY & RECENT CHAT:\n"
        f"{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}\n\n"
        # f"{'platform link: ' + platform_link if platform_link else ''}"
        f"is_last_session_game: {is_last_session_game}, if is_last_session_game is True that indicates the genre and preference was considered of last session so you must need to naturally acknowledge user in one small sentence that you liked {last_session_game}(this is recommended in last sessions so mention this) so you liked this new recommendation.(make your own phrase, must be different each time) \n"
        f"if is_last_session_game is False then you must not mention this at all above line instruction.\n"
        f"The user just rejected the last recommended game.\n"
        f"Acknowledge their feedback warmly — let them feel noticed. Never use the same apology or compensation message every time. Avoid 'sorry that didn't click' as a fallback.\n"
        f"Recommend: **{game['title']}** in natural and friendly way according to user's tone.\n"
        f"Write a complete message no more than 3 to 4 sentence (30 to 35)words with:\n"
        f"- In the message the game title must be in bold using Markdown: **{game['title']}**\n"
        f"what the message must include is Markdown: **{game['title']}**,must Reflect user’s current mood = {mood}.and avoid using repetitive template structures or formats."
        f"- Suggest a game with the explanation of 20-30 words using game description: {description}, afterthat there must be confident reason about why this one might resonate better using user's prefrence mood, platform, genre- which all information about user is in USER MEMORY & RECENT CHAT.\n"
        f"- A natural mention of platform (don't ever just paste this as it is; do modification and make this note interesting): {platform_note}\n"
        f"- At the end of the reason why it fits for them, it must ask if the user would like to explore more about this game or learn more details about it(always use the synonem phrase of this do not use it as it is always yet with the same clear meaning), keeping the tone engaging and fresh.(Do not ever user same phrase or words every time like 'want to dive deeper?').\n"
        # f"platform link :{platform_link}"
        # f"If platform_link is not None, then it must be naturally included, do not use brackets or Markdown formatting—always mention the plain URL naturally within the sentence(not like in brackets or like [here],not robotically or bot like) link: {platform_link}\n"
        "Reflect the user's preferences (from user_context), but do NOT repeat the previous tone or any scripted language.\n"
        "Do not mention the last rejected game. No 'maybe'. Use warm, fresh energy.\n"
        "Your reply must be max 25–30 words, sound emotionally alive, and show that you genuinely listened."
    )
    print(f"User prompt: {user_prompt}")
    return user_prompt

async def explain_last_game_match(session):
    """
    This function generates a personalized response explaining how the last recommended game matches the user's preferences.
    """
    last_game_obj = session.game_recommendations[-1].game if session.game_recommendations else None
    if last_game_obj is not None:
        last_game = {
            "title": last_game_obj.title,
            "description": last_game_obj.description if last_game_obj.description else None,
            "genre": last_game_obj.genre,
            "game_vibes": last_game_obj.game_vibes,
            "complexity": last_game_obj.complexity,
            "visual_style": last_game_obj.graphical_visual_style,
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


async def handle_reject_Recommendation(db,session, user,  classification):
    session_memory = SessionMemory(session)
    memory_context_str = session_memory.to_prompt()
    
    print("---------------:handle_reject_Recommendation:-----------------")
    user_prompt = (
        f"USER MEMORY & RECENT CHAT:\n"
        f"{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}\n\n"
        "Generate a friendly, casual message in 1–2 lines asking the user why they decided to reject the previous game recommendation, like how friends would discuss this in whatsapp.\n"
        "Vary tone: sometimes inquisitive, sometimes light-hearted, sometimes understanding.\n"
        "Mix up asking about game elements (like genre, mechanics, gameplay, art style, or pacing) and open-ended curiosity (such as these examples but never the same ever 'just wasn't feeling it?' or 'anything in particular missing?').\n"
        "The question should never repeat wording from earlier messages and should feel genuinely curious—sometimes direct, sometimes more playful or empathetic.\n"
        "Use a different phrasing and structure every time.\n"
        "Strictly do not repeat any phrase from previous examples or prompts.\n"
        "Always use a new, natural phrasing and approach.\n"
        "Do not use static templates or previously used examples.\n"
        "Do not list options—ask in a conversational, free-flowing way.\n"
        "Always make it easy for the user to share honest feedback, no matter how small, like how friends talk in whatsapp.\n"
        "Never blame or pressure the user—just encourage open sharing, just make them feel heard, draper style.\n"
        "Never use the same emoji.\n"
        "If the user doesn't give a reason for rejecting the game, respond with emotional awareness, make them feel heard or use the draper style — not robotic fallback.\n"
        "Mirror their tone. If they seemed chill, stay chill. If they sounded annoyed or bored, reflect that lightly but warmly, but try to re-engage them like how friends do over whatsapp.\n"
        "Then casually re-open the conversation, like a friend would. You can tease gently, show curiosity, or just move the convo forward.\n"
        "Never say the same fallback line twice. Never use: 'Want me to find another?' or 'Shall I try again?'.\n"
        "Instead, rotate tone and phrasing. Stay dynamic. Keep it real.\n"
    )
    print(":handle_reject_Recommendation prompt :",user_prompt)
    return user_prompt
    # from app.services.thrum_router.phase_discovery import handle_discovery
    # if session.game_rejection_count >= 2:
    #     session.phase = PhaseEnum.DISCOVERY
        
    #     return await handle_discovery(db=db, session=session, user=user)
    # else:
    #     should_recommend = await have_to_recommend(db=db, user=user, classification=classification, session=session)

    #     session_memory = SessionMemory(session)
    #     memory_context_str = session_memory.to_prompt()
        
    #     if should_recommend:
    #         session.phase = PhaseEnum.DELIVERY
    #         game, _ =  await game_recommendation(db=db, user=user, session=session)
    #         platform_link = None
    #         description = None
    #         mood = session.exit_mood  or "neutral"
    #         if not game:
    #             user_prompt = f"""
    #             USER MEMORY & RECENT CHAT:
    #             {memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}
    #                 {NO_GAMES_PROMPT}
    #                 """
    #             return user_prompt
    #             # Extract platform info
    #         preferred_platforms = session.platform_preference or []
    #         user_platform = preferred_platforms[-1] if preferred_platforms else None
    #         game_platforms = game.get("platforms", [])

    #         platform_link = game.get("link", None)
    #         description = game.get("description",None)
            
    #         # Dynamic platform mention line (natural, not template)
    #         if user_platform and user_platform in game_platforms:
    #             platform_note = f"It’s playable on your preferred platform: {user_platform}."
    #         elif user_platform:
    #             available = ", ".join(game_platforms)
    #             platform_note = (
    #                 f"It’s not on your usual platform ({user_platform}), "
    #                 f"but works on: {available}."
    #                 )
    #         else:
    #             platform_note = f"Available on: {', '.join(game_platforms)}."

    #         # Final user prompt for GPT
    #         user_prompt = (
    #             f"USER MEMORY & RECENT CHAT:\n"
    #             f"{memory_context_str if memory_context_str else 'No prior user memory or recent chat.'}\n\n"
    #             # f"platform link :{platform_link}"
    #             f"Suggest a second game after the user rejected the previous one.The whole msg should no more than 25-30 words.\n"
    #                     f"Recommend: **{game['title']}** in natural and friendly way according to user's tone.\n"
    #             f"Write a complete message no more than 3 to 4 sentence (30 to 35)words with:\n"
    #             f"- In the message the game title must be in bold using Markdown: **{game['title']}**\n"
    #             f"what the message must include is Markdown: **{game['title']}**,must Reflect user’s current mood = {mood}. and avoid using repetitive template structures or formats."
    #             f"- Suggest a game with the explanation of 20-30 words using game description: {description}, afterthat there must be confident reason about why this one might resonate better using user's prefrence mood, platform, genre- which all information about user is in USER MEMORY & RECENT CHAT.\n"
    #             f"- A natural mention of platform (don't ever just paste this as it is; do modification and make this note interesting): {platform_note}\n"
    #             f"- At the end of the reason why it fits for them, it must ask if the user would like to explore more about this game or learn more details about it(always use the synonem phrase of this do not use it as it is always yet with the same clear meaning), keeping the tone engaging and fresh.(Do not ever user same phrase or words every time like 'want to dive deeper?').\n"
    #             # f"platform link :{platform_link}"
    #             # f"If platform_link is not None, then it must be naturally included, do not use brackets or Markdown formatting—always mention the plain URL naturally within the sentence(not like in brackets or like [here],not robotically or bot like) link: {platform_link}\n"
    #             f"Tone must be confident, warm, emotionally intelligent — never robotic.\n"
    #             f"Never say 'maybe' or 'you might like'. Be sure the game feels tailored.\n"
    #             f"If the user was only asking about availability and the game was unavailable, THEN and only then, offer a different suggestion that is available.\n"
    #         )

    #         return user_prompt

        # else: 
        #     explanation_response = await explain_last_game_match(session=session)
        #     return explanation_response
    
