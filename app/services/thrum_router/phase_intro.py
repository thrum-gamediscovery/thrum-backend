import random
from app.services.general_prompts import GLOBAL_USER_PROMPT, FIRST_INTRO_PROMPTS, ANOTHER_INTRO_PROMPTS

async def handle_intro(session):

    user_name = session.user.name if session.user.name else ""
    tone = session.meta_data.get("tone", "")
    mood = session.meta_data.get("mood", "")
    last_game = session.last_recommended_game if session.last_recommended_game else ""
    platform = session.platform_preference if session.platform_preference else ""
        
    # Check if the user is a returning user
    if session.meta_data.get("returning_user"):
        return build_reengagement_intro(session)
    
    # Ensure the 'already_greet' key exists in metadata and set it to False if it's missing
    if session.meta_data.get("already_greet") is None:
        session.meta_data["already_greet"] = False  # Initialize if not present
    
    # If the user has not been greeted, greet them for the first time
    if not session.meta_data.get("already_greet"):
        session.meta_data["already_greet"] = True  # Mark as greeted
        return build_first_time_intro(user_name, tone, mood)
    
    # If the user has already been greeted, show another intro
    return another_intro(user_name, tone, mood, last_game, platform)

def build_first_time_intro(user_name="", tone="", mood=""):
    user_prompt = random.choice(FIRST_INTRO_PROMPTS)
    return user_prompt.format(user_name=user_name, tone=tone, mood=mood)

def another_intro(user_name="", tone="", mood="", last_game="", platform=""):
    user_prompt = random.choice(ANOTHER_INTRO_PROMPTS)

    return user_prompt.format(user_name=user_name, tone=tone, mood=mood, last_game=last_game, platform=platform, GLOBAL_USER_PROMPT=GLOBAL_USER_PROMPT)

def build_reengagement_intro(session):
    user_name = session.meta_data.get("user_name", "")
    if not user_name:
        user_name = "friend"  # Fallback if no name is available
    user_prompt = f"""
        {GLOBAL_USER_PROMPT}
        You’re Thrum, a warm, playful friend who remembers the user and welcomes them back after some time away.

        Create a short, natural, friendly welcome-back message in 3–5 short sentences, using casual language and 1–2 fitting emojis.  
        The tone is curious, upbeat, and inviting — like a friend catching up after a break.

        Examples to inspire you (don’t copy exactly):  
        - “You’re back 👀 How are you? Nice to see you again.”  
        - “How’s life been? Still hunting that next hit? Let’s pick up where we left off.”  

        Make sure to:  
        - Show that you remember them and their quest  
        - Invite them to continue chatting or discovering games  
        - Sound genuine, relaxed, and human  
        - Keep it under 40 words total
    """ 
    return user_prompt