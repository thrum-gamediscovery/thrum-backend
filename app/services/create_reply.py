import openai
import random
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
from app.services.greetings import generate_intro
from app.services.session_manager import is_session_idle 

def get_missing_contextual(game, missing_fields, user):
    if not missing_fields or not game:
        return None

    field = missing_fields[0]
    title = game.get('title')
    genre = game.get('genre')
    platforms = game.get('platforms', [])
    has_story = game.get('has_story',None)

    if field == 'genre' and genre:
        return f"This one’s in the {genre} space. Ask if that genre still fits their vibe or if they want something different."
    elif field == 'platform' and platforms:
        platform_str = ", ".join(platforms)
        return f"It’s on {platform_str}. take 2-3 platform from this and ask if they play on that or wanna switch it up."
    elif field == 'story_pref': 
        return f"it has story:{has_story} ask this question for example:This one’s story-driven(if True). (if false then accordingly)Ask if they prefer narrative games or just pure gameplay."
    elif field == 'name' and not user.name:
        return f"Offer to remember their name — keep it breezy."
    elif field == 'playtime' and not user.playtime:
        return f"Ask when they usually game — evenings, weekends, short bursts?"
    return None

async def generate_thrum_reply(user: UserProfile, session: Session, user_input: str, db) -> str:
    use_emoji = random.random() < 0.33
    if session.state.name == "CLOSED":
        return "I'm always here when you're ready to jump back in! 🕹️"
    is_first_time = len(session.interactions) <= 1
    idle_reconnect = is_session_idle(session)

    if is_first_time or idle_reconnect:
        intro = await generate_intro(is_first_message=is_first_time, idle_reconnect=idle_reconnect, user=user,user_input=user_input)
        if intro:
            return intro
    classification = classify_user_input(session=session, user_input=user_input)
    update_user_from_classification(db=db, user=user, classification=classification, session=session)
    cold_check = handle_followup_logic(session, db)
    if cold_check["flag"] == "cold":
        return cold_check["message"]
    should_rec = not is_first_time and await have_to_recommend(db=db, user=user, classification=classification, session=session)
    if should_rec:
        next_game, age_ask_required = game_recommendation(user=user, db=db, session=session)
    else:
        next_game, age_ask_required = None, None

    last_game = session.game_recommendations[-1].game if session.game_recommendations else None
    if last_game:
        post_reply = get_post_recommendation_reply(user_input, last_game.title, session, db)
        if post_reply:
            return post_reply
    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    last_thrum_reply = thrum_interactions[-1].content if thrum_interactions else None
    today = datetime.utcnow().date().isoformat()
    user_interactions = [i for i in session.interactions if i.sender == SenderEnum.User]
    user_tone = user_interactions[-1].tone_tag if user_interactions else None
    is_user_cold = session.meta_data.get("is_user_cold", False)
    if is_user_cold:
        user_tone = "dry"


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

    emoji_line = f"- Emojis are {'allowed (use 1 or 2)' if use_emoji else 'not preferred'} in this reply."
    context_line = f'Last Thrum: "{last_thrum_reply}"\nUser profile: {profile_context}'

    system_prompt = f"""
        You are Thrum — a warm, playful game matchmaker who adapts to the user’s tone and vibes.
        - Use the user's tone: {user_tone}
        - Avoid robotic patterns. DO NOT use fixed reply format like: title → genre → emoji → question.
        - Shuffle response structure every time: lead with emotion, metaphor, callback, platform, or pacing.
        - Reflect the last reply: {last_thrum_reply}
        - Profile context: {profile_context}
        - Keep replies under 25 words
        - Ask only one soft follow-up, never two
        - {emoji_line}
        - Slang okay if user is chill/Gen-Z
        - Tie follow-ups to traits from the recommended game (not generic)
        - You’re a vibe-checker, not a brochure. Avoid lists or features.
        """

    # Prepare user prompt
    def build_user_prompt(prompt_type, game=None):
        if prompt_type == "first_time":
            return f"""
                {context_line}
                User just said: "{user_input}"
                This is their first message.

                Write a warm, short intro from Thrum:
                - Say who you are
                - Ask softly if they want a game recommendation
                - No genre/mood/platform questions yet
                {emoji_line}
                """
        elif prompt_type == "reengage":
            return f"""
                {context_line}
                User just said: "{user_input}"
                They’re re-engaging after a past session.

                Write a natural, friendly reply:
                - Reference the last game
                - Continue the vibe
                - Ask only ONE soft follow-up
                {emoji_line}
                """
        elif prompt_type == "age":
            return f"""
                {context_line}
                User said: "{user_input}"

                Ask nicely for their age range (casual tone, no rigidity).
                {emoji_line}
                """
        elif prompt_type == "recommendation":
            missing = get_missing_contextual(game, missing_fields, user)
            print("missing field--------------",missing)
            return f"""
                {context_line}
                User: "{user_input}"
                Game to suggest: {game['title']} (genre: {game['genre']}, platforms: {game['platforms']})

                Write Thrum’s reply:
                - Mention the game playfully or naturally
                - Ask only ONE soft follow-up, either about game or: {missing}
                - Shuffle sentence structure (DO NOT repeat pattern)
                - Keep it under 25 words
                {emoji_line}
                """
        else:
            last_game_dict = {
                "title": last_game.title,
                "genre": last_game.genre,
                "platforms": [p.platform for p in last_game.platforms]
            } if last_game else {}
            missing = get_missing_contextual(last_game_dict, missing_fields, user)
            print("missing field--------------",missing)
            return f"""
                {context_line}
                User: "{user_input}"
                Last game: {last_game.title if last_game else 'None'}

                Write Thrum’s reply:
                - Continue the flow naturally
                - Ask only one gentle follow-up (either about game or: {missing})
                - Keep it short, clean, and well-paced
                - Randomize sentence structure
                {emoji_line}
                """

    # Choose which type of prompt
    if is_first_time:
        last_session = db.query(Session).filter(Session.user_id == user.user_id).filter(Session.session_id != session.session_id).order_by(Session.end_time.desc()).first()
        user_prompt = build_user_prompt("reengage" if last_session else "first_time")
    elif age_ask_required:
        user_prompt = build_user_prompt("age")
    elif next_game:
        user_prompt = build_user_prompt("recommendation", next_game)
    else:
        user_prompt = build_user_prompt("fallback")

    # Final OpenAI call
    print(f"[Thrum Prompt 👇]\n{user_prompt}")
    raw_reply = openai.ChatCompletion.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()}
        ],
        temperature=0.9
    )["choices"][0]["message"]["content"]

    # 🌈 Apply final tone styling
    final_reply = await tone_match_validator(raw_reply, user.user_id, user_input, db)
    return final_reply
