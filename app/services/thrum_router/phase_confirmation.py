from app.db.models.enums import SenderEnum, PhaseEnum
from app.db.models.game import Game
from app.db.models.game_platforms import GamePlatform
from app.services.thrum_router.phase_delivery import get_recommend
from app.utils.link_helpers import maybe_add_link_hint
import random
from app.utils.whatsapp import send_whatsapp_message
from app.services.modify_thrum_reply import format_reply
from app.services.general_prompts import GLOBAL_USER_PROMPT, GAME_LIKED_FEEDBACK, ALREADY_PLAYED_GAME, GAME_LIKED_NOT_PLAYED, PROFILE_SNAPSHOT, CONFIRMATION_PROMPTS, ASK_NAME

def get_unique_prompt(session, prompt_list, meta_key):
    session.meta_data = session.meta_data or {}
    used = session.meta_data.get(meta_key, [])
    all_indexes = list(range(len(prompt_list)))
    unused = [i for i in all_indexes if i not in used]
    if not unused:
        used = []
        unused = all_indexes
    chosen = random.choice(unused)
    used.append(chosen)
    session.meta_data[meta_key] = used
    return prompt_list[chosen]

async def handle_confirmed_game(db, user, session, classification):
    """
    Handle when user accepts a game recommendation.
    
    Following client specs:
    - 1-2 lines max
    - Match user's emotional tone
    - Ask them to share back later (creates emotional stickiness)
    - Never say "hope you enjoy" or "thanks"
    - Keep it playful, curious, or chill based on their tone
    """
    if classification.get("find_game", None) is None or classification.get("find_game") == "None":
        prompt = f"""
            {GLOBAL_USER_PROMPT}
            ---
            You don't know which game the user is asking or talking about. Ask them which game they're talking about in a friendly way. Keep it brief and natural.
        """.strip()
        return prompt
    game_id = session.meta_data.get("find_game")
    game = db.query(Game).filter_by(game_id=game_id).first()
    game_title = game.title
    session.meta_data['liked_followup'] = True
    tone = session.meta_data.get("tone", "friendly")
    
    # 1. Get user's last message (optional, but keep if you use user_input below)
    sorted_interactions = sorted(session.interactions, key=lambda i: i.timestamp, reverse=True)
    user_interactions = [i for i in sorted_interactions if i.sender == SenderEnum.User]
    user_input = user_interactions[0].content if user_interactions else ""

    # 2. Get all platforms available for this game
    platform_rows = db.query(GamePlatform.platform).filter_by(game_id=game_id).all()
    platform_list = [p[0] for p in platform_rows] if platform_rows else []

    # 3. Find user's preferred platform (last non-empty entry)
    platform_preference = None
    if session.platform_preference:
        non_empty = [p for p in session.platform_preference if p]
        if non_empty:
            platform_preference = non_empty[-1]

    # 4. Fallback: if no user preference, pick the first available platform for this game
    if not platform_preference:
        gameplatform_row = db.query(GamePlatform).filter_by(game_id=game_id).first()
        if gameplatform_row:
            platform_preference = gameplatform_row.platform

    # 5. Fetch the platform link for that game/platform (if any)
    platform_link = None
    if platform_preference:
        gp_row = db.query(GamePlatform).filter_by(game_id=game_id, platform=platform_preference).first()
        if gp_row and gp_row.link:
            platform_link = gp_row.link

    # 6. If still no link (e.g. platform missing, no user preference, or no link for that platform), fallback: any available link for this game
    if not platform_link:
        print("No preferred platform found for user #############")
        gp_row = db.query(GamePlatform).filter(GamePlatform.game_id == game_id, GamePlatform.link != None).first()
        if gp_row:
            platform_preference = gp_row.platform
            platform_link = gp_row.link

    # Get memory context for personalization
    memory_context = ""
    if session.meta_data:
        name = session.meta_data.get("name", "")
        platform = session.meta_data.get("platform", "")
        genre_likes = session.meta_data.get("genre_likes", [])
        genre_dislikes = session.meta_data.get("genre_dislikes", [])
        
        memory_context = f"""
            Memory context:
            - Name: {name}
            - Platform: {platform}
            - Likes: {genre_likes}
            - Dislikes: {genre_dislikes}
            - User tone: {tone}
            """
    
    if not session.meta_data.get("played_yet", False):
        # First time accepting this game: use cycling prompt
        prompt = get_unique_prompt(session, GAME_LIKED_NOT_PLAYED, "game_liked_not_played")
        user_prompt=  prompt.format(GLOBAL_USER_PROMPT=GLOBAL_USER_PROMPT,user_input=user_input,tone=tone,platform_preference=platform_preference)
        
        # Mark that we've handled first acceptance
        if session.meta_data is None:
            session.meta_data = {}
        session.meta_data["played_yet"] = True
        
    else:
        # They've played and are giving feedback
        if session.meta_data.get("ask_confirmation", True):
            prompt = get_unique_prompt(session, ALREADY_PLAYED_GAME, "already_played_game")
            user_prompt=  prompt.format(GLOBAL_USER_PROMPT=GLOBAL_USER_PROMPT,user_input=user_input,tone=tone)
            
            session.meta_data["ask_confirmation"] = False
            
        else:
            prompt = get_unique_prompt(session, GAME_LIKED_FEEDBACK, "game_liked_feedback")
            user_prompt=  prompt.format(GLOBAL_USER_PROMPT=GLOBAL_USER_PROMPT,game_title=game_title,tone=tone)

    user_prompt = await maybe_add_link_hint(db, session, user_prompt, platform_link)
    # Initialize metadata if needed
    if session.meta_data is None:
        session.meta_data = {}
    if not session.meta_data.get('ask_for_link'):
        # Set default values
        if 'ask_for_rec_friend' not in session.meta_data:
            session.meta_data['ask_for_rec_friend'] = True
            db.commit()
        print(f"++++++++++++++++++++++++++++== meta_data : {session.meta_data} : dont_give_name : {'dont_give_name' not in session.meta_data}")
        if "dont_give_name" not in session.meta_data:
            print(f"------------------------------------- dont_give_name checkkkk -----------------------")
            if user.name is None:
                reply = await format_reply(db=db, session=session, user_input=user_input, user_prompt=user_prompt)
                await send_whatsapp_message(user.phone_number, reply)
                print("Setting default metadata for session")
                session.meta_data["dont_give_name"] = True
                session.meta_data["give_name"] = True
                db.commit()
                prompt = random.choice(ASK_NAME)
                return prompt
            else:
                session.meta_data["dont_give_name"] = True
                db.commit()
        
    return user_prompt

async def confirm_input_summary(db, session, user, user_input) -> str:
    """
    Uses varied confirmation prompts to generate unique, human-sounding confirmation lines.
    Rotates between different prompt styles based on session context.
    """
    mood = session.exit_mood if session.exit_mood is not None else ""
    genre_list = session.genre or []
    platform_list = session.platform_preference or []
    genre = genre_list[-1] if isinstance(genre_list, list) and genre_list else ""
    platform = platform_list[-1] if isinstance(platform_list, list) and platform_list else ""
    tone = session.meta_data.get("tone", "neutral")
    
    if not any([mood, genre, platform]):
        return "Got it — let me find something for you."
    
    # Select prompt variant based on session context
    if mood in ["excited", "hyped", "energetic"]:
        prompt_index = 0  # CONFIRMATION MOMENT
    elif tone in ["chill", "relaxed", "calm"]:
        prompt_index = 1  # VIBE CHECK COMPLETE
    elif session.game_rejection_count > 0:
        prompt_index = 2  # LOCKED AND LOADED
    else:
        prompt_index = 3  # FREQUENCY MATCHED
    
    prompt = CONFIRMATION_PROMPTS[prompt_index]
    user_prompt = prompt.format(
        GLOBAL_USER_PROMPT=GLOBAL_USER_PROMPT,
        mood=mood,
        genre=genre,
        platform=platform,
        tone=tone
    )
    session.phase = PhaseEnum.CONFIRMATION
    db.commit()
    reply = await format_reply(db=db,session=session, user_input=user_input, user_prompt=user_prompt)
    await send_whatsapp_message(user.phone_number, reply)
    session.phase = PhaseEnum.DELIVERY
    db.commit()
    user_prompt = await get_recommend(db=db, session=session, user=user)
    return user_prompt
