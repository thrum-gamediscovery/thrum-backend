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
from app.services.tone_engine import tone_match_validator
from app.tasks.followup import handle_followup_logic, get_post_recommendation_reply

async def generate_thrum_reply(user: UserProfile, session: Session, user_input: str, db) -> str:
    is_first_time = len(session.interactions) == 1
    classification = classify_user_input(session=session, user_input=user_input)
    update_user_from_classification(db=db, user=user, classification=classification, session=session)
    cold_check = handle_followup_logic(session, db)
    if cold_check["flag"] == "cold":
        return cold_check["message"]
    should_rec = not is_first_time and await have_to_recommend(db=db, user=user, classification=classification, session=session)
    should_rec = True
    if should_rec:
        next_game, age_ask_required = game_recommendation(user=user, db=db, session=session)
    else:
        next_game, age_ask_required = None, None

    last_game = session.game_recommendations[-1].game if session.game_recommendations else None
    if last_game:
        post_reply = get_post_recommendation_reply(user_input, last_game.name, session, db)
        if post_reply:
            return post_reply
    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    last_thrum_reply = thrum_interactions[-1].content if thrum_interactions else None
    today = datetime.utcnow().date().isoformat()
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

    missing_fields = []
    if not user.genre_prefs: missing_fields.append("genre")
    if not user.platform_prefs: missing_fields.append("platform")
    if user.story_pref is None: missing_fields.append("story_pref")
    if not user.name: missing_fields.append("name")
    if not user.playtime: missing_fields.append("playtime")

    def get_missing(game, missing_fields):
        if not missing_fields:
            return ''
        field = missing_fields[0]
        if field == 'genre':
            prompt = f"This one leans {game['genre']} do not talk about all genre just talk for one or two — does that sound like your kind of game, or would you rather try something different?"
        elif field == 'platform':
            prompt = f'you usually game on one of those, or something else? just curious - ask this question based on new games platform or previous game platform.'
        elif field == 'story_pref':
            prompt = f'do you want to enjoy games with a story, or prefer more gameplay-driven stuff? If the game is story-driven, ask if they want more like this.'
        elif field == 'name':
            prompt = f'BTW, I can remember your name for next time if you want – totally optional!'
        elif field == 'playtime':
            prompt = f'When do you usually get your game time in? Evenings, weekends, random breaks? Just helps me time my picks better ⏰'
        return f"- Ask like this: {prompt}"

    system_prompt = (
        "You are Thrum, a warm and playful game matchmaker. "
        f"you must must must have to use {user_tone} tone to create thrum reply."
        "Reusing the user’s own language intelligently, not just mimicking it"
        "Keep it under 20 words. Add 1–2 emojis that match the user's mood."
        "Each reply should: (1) feel like part of a real conversation, (2) suggest a game *only if appropriate*, and (3) ask one soft follow-up. "
        "Never ask multiple questions at once. Never list features. Never say 'as an AI'."
        "Make reply based on user's tone. Use short forms if user is using that."
        "Reflect user choices more visibly. Show adaptive memory."
        "If there is any missing field then the question should always relate to the previous game."
    )

    if is_first_time:
        last_session = db.query(Session).filter(Session.user_id == user.user_id).filter(Session.session_id != session.session_id).order_by(Session.end_time.desc()).first()
        user_is_reengaging = last_session and last_session.state.name in ["PASSIVE", "COLD"]
        if user_is_reengaging:
            last_game = db.query(GameRecommendation).filter(GameRecommendation.user_id == user.user_id).order_by(GameRecommendation.timestamp.desc()).first()
            user_prompt = f"""
                Write a natural, friendly reply from Thrum that:
                - References the last game briefly
                - Ties it to the genre they were into earlier
                - Feels like a relaxed continuation of the last chat
                - Optionally asks one soft follow-up (from get_missing if any)
                - Max 25 words, include 2 casual emojis
            """
        else:
            user_prompt = f"""
                The user just said: \"{user_input}\"
                This is their first message.
                Write a friendly first reply from Thrum, introducing who you are.
                Ask softly if they want a game recommendation. Use casual, low-pressure tone.
                Avoid recommending a game yet. Keep it warm and short.
            """
    elif age_ask_required:
        user_prompt = f"""
            The user just said: \"{user_input}\"
            Ask gently for age range before recommending. Make it warm, respectful, and casual.
        """
    elif next_game:
        user_prompt = f"""
            User just said: \"{user_input}\"
            Game to suggest now: \"{next_game}\"
            User profile: {profile_context}
            Write Thrum’s reply:
            - Mention the game casually (highlight name)
            - Match the user's tone and mood
            {get_missing(game=next_game, missing_fields=missing_fields)}
            - Ask one soft follow-up based on that game
            - Keep it under 25 words with 2–3 emojis
        """
    else:
        user_prompt = f"""
            User just said: \"{user_input}\"
            last suggested game: \"{last_game}\"
            Write Thrum’s reply:
            - Match the tone and reflect past preferences
            {get_missing(game=last_game, missing_fields=missing_fields)}
            - Tie the next question to the last suggestion
            - Keep it under 25 words with 2–3 emojis
        """

    raw_reply = openai.ChatCompletion.create(
        model='gpt-4.1-mini',
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.9
    )["choices"][0]["message"]["content"]

    # 🌈 Apply final tone styling
    final_reply = await tone_match_validator(raw_reply, user.user_id, user_input, db)
    return final_reply
