# 📄 File: generate_thrum_reply.py

import openai
from datetime import datetime
from app.services.mood_engine import detect_mood_from_text
from app.services.game_recommend import game_recommendation
from app.services.input_classifier import classify_user_input, have_to_recommend
from app.services.user_profile_update import update_user_from_classification
from app.db.models.enums import SenderEnum
from app.db.models.session import Session
from app.db.models.game_recommendations import GameRecommendation
from app.db.models.user_profile import UserProfile

async def generate_thrum_reply(user: UserProfile, session: Session, user_input: str, db) -> str:
    # Detect mood (for profile and session)
    is_first_time = len(session.interactions) == 1
  
    # Classify new profile signals (genre, vibe, platform, etc.)
    classification = classify_user_input(session=session, user_input=user_input)
    update_user_from_classification(db=db, user=user, classification=classification,session=session)
    if not is_first_time:
        should_rec = await have_to_recommend(db=db, user=user, classification=classification, session=session)
    else:
        should_rec = False
    print(f"have_to_rec : {should_rec}")
    # 🎯 Get recommended games based on profile
    should_rec = True
    if should_rec:
        next_game, age_ask_required = game_recommendation(user=user, db=db, session=session)

    else:
        next_game, age_ask_required = None, None

    # 🔁 Get last recommendation and mood
    last_game = session.game_recommendations[-1].game if session.game_recommendations else None
    print(f"last_game : {last_game}")
    
    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    last_thrum_reply = thrum_interactions[-1].content if thrum_interactions else None
    print(f"[🧠] Last Thrum reply: {last_thrum_reply}")
    today = datetime.utcnow().date().isoformat()
    # 🧠 Build context JSON for GPT
    user_interactions = [i for i in session.interactions if i.sender == SenderEnum.User]
    user_tone = user_interactions[-1].tone_tag if user_interactions else None
    profile_context = {
        "name": user.name,
        "mood": user.mood_tags.get(today),
        "genre_interest": user.genre_prefs.get(today),
        "platform": user.platform_prefs,
        "region": user.region,
        "playtime": user.playtime,
        "reject_tags": user.reject_tags
    }
    # 🕵️‍♂️ Figure out which field is unknown
    missing_fields = []
    if not user.genre_prefs: missing_fields.append("genre")
    if not user.platform_prefs: missing_fields.append("platform")
    if user.story_pref is None: missing_fields.append("story_pref")
    if not user.name: missing_fields.append("name")
    if not user.playtime: missing_fields.append("playtime")

    def get_missing(game, missing_fields):
        print(f" get gane : {game}")
        if not missing_fields:
            return ''  # Nothing to ask
        field = missing_fields[0]

        if field == 'genre':
            prompt = f"This one leans {game['genre']} do not talk about all genre just talk for one or two — does that sound like your kind of game, or would you rather try something different?"

        elif field == 'platform':
            prompt = f'you usually game on one of those, or something else? just curious - ask this question based on new games platform or previous game platform like. like this game is on this many platform do you like to play on this platform or have other preferences?'

        elif field == 'story_pref':
            prompt = f'do you want to enjoy games with a story, or prefer more gameplay-driven stuff? and make this question accoding the value of previous game or new games story pref.like if the game is already storydriven then ask like this is sotry driven want to play more like this or not?'

        elif field == 'name':
            prompt = f'BTW, I can remember your name for next time if you want – totally optional!'

        elif field == 'playtime':
            prompt = f'When do you usually get your game time in? Evenings, weekends, random breaks? Just helps me time my picks better ⏰'

        return f"- Ask like this: {prompt} (and dont ever repeat the same word structure question make that little changed each time)( dont just like this ask based on user's tone and mood)" if prompt else ''
    
    system_prompt = (
        "You are Thrum, a warm and playful game matchmaker. "
        "Your tone is cozy, human, and emoji-friendly. Never robotic. Never generic. "
        f"you must must must have to use {user_tone} tone to create thrum reply."
        "Reusing the user’s own language intelligently, not just mimicking it"
        "Keep it under 20 words. Add 1–2 emojis that match the user's mood. if user prefer small answer so give user short reply"
        "Each reply should: (1) feel like part of a real conversation, (2) suggest a game *only if appropriate*, and (3) ask one soft follow-up. "
        "Never ask multiple questions at once. Never list features. Never say 'as an AI'. Never break character. "
        "in one reply there should not be two questions, if you are asking one question then do not ask another question in same reply."
        "Make reply based on user's tone. You can use short forms if user is using that."
        "if user is providing their favourite genre or game or platform then just make reply that shows that it is noticed."
        "if user input is about specific game, genre, or platform liking or not liking then just Reflecting user choices more visibly,Showing adaptive memory to that like example: 'Noted. I won’t push puzzle-platformers again unless you say so'. it's just an example do not copy this make your own."
        "If there is any missing field then the question of that field should always relate to the previous game (e.g., contrast it, ask if they'd like more/less of a trait)"
    )
    if is_first_time:
        last_session = (
        db.query(Session)
        .filter(Session.user_id == user.user_id)
        .filter(Session.session_id != session.session_id)
        .order_by(Session.end_time.desc())
        .first()
    )

        if last_session:
            print(f'last session state : {last_session} ::::: {last_session.state}')
            if last_session.state.name in ["PASSIVE", "COLD"]:
                print("⚠️ Last session was passive or cold.")
                # Optionally: set a flag or trigger a specific prompt
                user_is_reengaging = True
            else:
                user_is_reengaging = False
        else:
            user_is_reengaging = False

        if user_is_reengaging:
            last_game = ( db.query(GameRecommendation)
                .filter(GameRecommendation.user_id == user.user_id)
                .order_by(GameRecommendation.timestamp.desc())
                .first()
            )
            user_prompt = f"""
                Write a natural, friendly reply from Thrum that:
                - References the last game briefly, maybe checking in on it
                - Ties it to the genre they were into earlier
                - Feels like a relaxed continuation of the last chat
                - Optionally asks one soft follow-up (from get_missing if any)
                - Keep the tone light and warm, like picking up where you left off
                - Max 25 words, include 2 casual emojis
            """
        else : 
            user_prompt = f"""
        The user just said: "{user_input}"
        This is their first message.

        Write a friendly first reply from Thrum, introducing who you are.
        Ask softly if they want a game recommendation. Use casual, low-pressure tone.
        Avoid recommending a game yet. Keep it warm and short.
        """
    elif age_ask_required:
        user_prompt = f"""
            The user just said: "{user_input}"
            This is important — the game match might be age-restricted.

            Thrum should **not** suggest the game yet.
            Instead, ask gently: "just to make sure I don’t suggest something too grown-up… mind sharing your age range?"
            Make it warm, respectful, and casual.don't use same words as above, make it different each time.
            """
    elif next_game:
        user_prompt = f"""
    User just said: "{user_input}"
    Your last message was: "{last_thrum_reply}"
    Game to suggest now: "{next_game}"

    User profile: {profile_context}

    Write Thrum’s reply:
    - if the user input is liking or disliking genre, game, or platform then just react to that like example:"Noted. I won’t push puzzle-platformers again unless you say so". it's just an example do not copy this make your own.
    - Mention the game casually(make it interesting with all data for that game)(game name should be highlighted) with user's profile if have but do not add all context just show one or last.
    - Match the user's tone and mood
    {get_missing(game=next_game,missing_fields=missing_fields)}
    - Your follow-up question should always relate to the suggested game (e.g., contrast it, ask if they'd like more/less of a trait)
    - Never switch to an unrelated topic suddenly.
    - Do not suggest any game by you only suggest which is given.
    Keep it under 25 words. Add 2–3 emojis that match the tone.
    """
        
    # CASE 4: NO GAME TO RECOMMEND
    else:
        user_prompt = f"""
    User just said: "{user_input}"
    Your last message was: "{last_thrum_reply}"
    last suggested game : "{last_game}"

    User profile: {profile_context}

    Write Thrum’s reply:
    - if the user input is liking or disliking genre, game, or platform then just react to that like example:"Noted. I won’t push puzzle-platformers again unless you say so". it's just an example do not copy this make your own.
    - discribe last suggested game shortly based on user's last input.
    - Match the user's tone and mood
    {get_missing(game=last_game,missing_fields=missing_fields)}
    - Your follow-up question should always relate to the last suggested game (e.g., contrast it, ask if they'd like more/less of a trait)
    - Never switch to an unrelated topic suddenly.
    - Do not suggest any game by you only suggest which is given.
    Keep it under 25 words. Add 2–3 emojis that match the tone.
    """
    print(f"user propmt : {user_prompt}")
    response = openai.ChatCompletion.create(
        model='gpt-4.1-mini',
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.9
    )
    return response["choices"][0]["message"]["content"]