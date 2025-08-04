from app.db.models.enums import SenderEnum
from app.db.models.game import Game
from app.db.models.game_platforms import GamePlatform
from app.utils.link_helpers import maybe_add_link_hint
import random
from app.services.general_prompts import GLOBAL_USER_PROMPT,GAME_LIKED_FEEDBACK, ALREADY_PLAYED_GAME, GAME_LIKED_NOT_PLAYED, PROFILE_SNAPSHOT, CONFIRMATION_PROMPTS

async def handle_confirmed_game(db, user, session):
    """
    Handle when user accepts a game recommendation.
    
    Following client specs:
    - 1-2 lines max
    - Match user's emotional tone
    - Ask them to share back later (creates emotional stickiness)
    - Never say "hope you enjoy" or "thanks"
    - Keep it playful, curious, or chill based on their tone
    """
    game_title = session.last_recommended_game
    game_id = db.query(Game).filter_by(title=game_title).first().game_id if game_title else None
    tone = session.meta_data.get("tone", "friendly")
    
    user_interactions = [i for i in session.interactions if i.sender == SenderEnum.User]
    user_input = user_interactions[-1].content if user_interactions else ""
    platform_rows = db.query(GamePlatform.platform).filter_by(game_id=game_id).all()
    platform_list = [p[0] for p in platform_rows] if platform_rows else []
    # Get user's preferred platform (last non-empty entry in the array)
    platform_preference = None
    if session.platform_preference:
        non_empty = [p for p in session.platform_preference if p]
        if non_empty:
            platform_preference = non_empty[-1]
    else:
        gameplatform_row = db.query(GamePlatform).filter_by(game_id=game_id).first()
        platform_preference = gameplatform_row.platform
    # Fetch the platform link for that game and platform
    platform_link = None
    if platform_preference:
        gp_row = db.query(GamePlatform).filter_by(game_id=game_id, platform=platform_preference).first()
        if gp_row:
            platform_link = gp_row.link  # This is the URL/link for the user's preferred platform
    else:
        print(f"`No preferred platform found for user #############`")
        gp_row = (
            db.query(GamePlatform)
            .filter(GamePlatform.game_id == game_id, GamePlatform.link != None)
            .first()
        )
        platform_link = gp_row.link if gp_row else None
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
        
        # First time accepting this game
        prompt = random.choice(GAME_LIKED_NOT_PLAYED)
        user_prompt=  prompt.format(GLOBAL_USER_PROMPT=GLOBAL_USER_PROMPT,user_input=user_input,tone=tone,platform_preference=platform_preference)
        
        # Mark that we've handled first acceptance
        if session.meta_data is None:
            session.meta_data = {}
        session.meta_data["played_yet"] = True
        
    else:
        # They've played and are giving feedback
        if session.meta_data.get("ask_confirmation", True):
            prompt = random.choice(ALREADY_PLAYED_GAME)
            user_prompt=  prompt.format(GLOBAL_USER_PROMPT=GLOBAL_USER_PROMPT,user_input=user_input,tone=tone)
            
            session.meta_data["ask_confirmation"] = False
            
        else:
            prompt = random.choice(GAME_LIKED_FEEDBACK)
            user_prompt=  prompt.format(GLOBAL_USER_PROMPT=GLOBAL_USER_PROMPT,game_title=game_title,tone=tone)

    user_prompt = await maybe_add_link_hint(db, session, user_prompt, platform_link)
    # Initialize metadata if needed
    if session.meta_data is None:
        session.meta_data = {}
    if not session.meta_data.get('ask_for_link'):
        # Set default values
        if "dont_give_name" not in session.meta_data:
            print("Setting default metadata for session")
            session.meta_data["dont_give_name"] = False
        if 'ask_for_rec_friend' not in session.meta_data:
            session.meta_data['ask_for_rec_friend'] = True
        db.commit()
    return user_prompt

async def confirm_input_summary(session) -> str:
    """
    Uses varied confirmation prompts to generate unique, human-sounding confirmation lines.
    Rotates between different prompt styles based on session context.
    """
    session.intent_override_triggered = True
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
    return user_prompt 
