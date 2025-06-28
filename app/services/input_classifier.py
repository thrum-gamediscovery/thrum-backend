import openai
import os
import json
from rapidfuzz import process
from openai import OpenAIError
from datetime import date, datetime
from sqlalchemy.orm import Session
from app.db.models.enums import SenderEnum
from app.db.models.session import Session
from sqlalchemy.dialects.postgresql import UUID
from app.db.models.game_recommendations import GameRecommendation
from app.db.models.user_profile import UserProfile

from app.db.models import Game
from app.services.mood_engine import detect_mood_from_text
from app.services.session_manager import update_or_create_session_mood
from app.utils.genre import get_best_genre_match 
from app.utils.platform_utils import get_best_platform_match

openai.api_key = os.getenv("OPENAI_API_KEY")

def resolve_game_id(db, game_text: str, session) -> UUID | None:
    # Get all titles
    all_games = db.query(Game.game_id, Game.title).all()
    title_lookup = {g.title: g.game_id for g in all_games}
    matches = process.extractOne(game_text, list(title_lookup.keys()), score_cutoff=75)

    return title_lookup[matches[0]] if matches else None

def update_game_feedback_from_json(db, user_id: UUID, feedback_data: list) -> None:

    if not isinstance(feedback_data, list) or not feedback_data:
        print("🟡 No valid game feedback provided. Skipping update.")
        return

    # Load all game titles and IDs
    all_games = db.query(Game.game_id, Game.title).all()
    title_lookup = {g.title: g.game_id for g in all_games}

    user = db.query(UserProfile).filter_by(user_id=user_id).first()
    if not user:
        print("❌ User not found.")
        return

    user.likes = user.likes or {}
    user.dislikes = user.dislikes or {}
    user.likes.setdefault("like", [])
    user.dislikes.setdefault("dislike", [])

    for feedback in feedback_data:
        game_title = feedback.get("game", "")
        accepted = feedback.get("accepted", None)
        reason = feedback.get("reason", "").strip()

        match = process.extractOne(game_title, list(title_lookup.keys()), score_cutoff=75)
        if not match:
            print(f"❌ No match found for game title: {game_title}")
            continue

        matched_title = match[0]
        matched_game_id = title_lookup[matched_title]
        print(f"🎯 Matched '{game_title}' → '{matched_title}' (ID: {matched_game_id})")

        # Try to find existing recommendation
        game_rec = db.query(GameRecommendation).filter_by(user_id=user_id, game_id=matched_game_id).first()

        if not game_rec:
            print(f"⚠️ No GameRecommendation found for game '{matched_title}' and user. Creating new entry.")
            game_rec = GameRecommendation(
                session_id=None,  # Optional: pass actual session if available
                user_id=user_id,
                game_id=matched_game_id,
                accepted=accepted,
                reason=reason
            )
            db.add(game_rec)
        else:
            game_rec.accepted = accepted
            game_rec.reason = reason
            print(f"✅ Updated: accepted={accepted}, reason='{reason}'")

        # Update user profile like/dislike
        if accepted is True and str(matched_game_id) not in user.likes["like"]:
            user.likes["like"].append(str(matched_game_id))
            print(f"👍 Added to likes: {matched_game_id}")
        elif accepted is False and str(matched_game_id) not in user.dislikes["dislike"]:
            user.dislikes["dislike"].append(str(matched_game_id))
            print(f"👎 Added to dislikes: {matched_game_id}")

    db.commit()
    print("💾 All feedback processed and saved.")




# ✅ Update user profile with parsed classification fields
def update_user_from_classification(db: Session, user, classification: dict,session):
    today = date.today().isoformat()

    name = classification.get("name")
    mood = classification.get("mood")
    game_vibe = classification.get("game_vibe")
    genre = classification.get("genre")
    platform = classification.get("platform_pref")
    region = classification.get("region")
    age = classification.get("age")
    story_pref = classification.get("story_pref")
    playtime = classification.get("playtime_pref")
    reject_tags = classification.get("regect_tag", [])
    game_feedback = classification.get("game_feedback", [])

    # -- Name
    if name and name != "None":
        user.name = name.strip().title()
        user.last_updated["name"] = str(datetime.utcnow())

    # -- Mood
    if mood and mood != "None":
        mood_result = detect_mood_from_text(db, mood)
        user.mood_tags[today] = mood_result
        user.last_updated["mood_tags"] = str(datetime.utcnow())
        # update_or_create_session_mood(db, user, new_mood=mood_result)

    # -- Game Vibe
    if game_vibe and game_vibe != "None":
        user.game_vibe = game_vibe.lower()
        user.last_updated["game_vibe"] = str(datetime.utcnow())

    # -- Genre Preferences
    if genre and genre != "None":
        matched_genre = get_best_genre_match(db=db, input_genre=genre)
        if matched_genre:
            user.genre_prefs.setdefault(today, [])
            if matched_genre not in user.genre_prefs[today]:
                user.genre_prefs[today].append(matched_genre)
            user.last_updated["genre_prefs"] = str(datetime.utcnow())

    # -- Platform Preferences
    if platform and platform != "None":
        matched_platform = get_best_platform_match(db=db, user_input=platform)
        if matched_platform:
            user.platform_prefs.setdefault(today, [])
            if matched_platform not in user.platform_prefs[today]:
                user.platform_prefs[today].append(matched_platform)
            user.last_updated["platform_prefs"] = str(datetime.utcnow())

    # -- Region
    if region and region != "None":
        user.region = region.strip().title()
        user.last_updated["region"] = str(datetime.utcnow())

    # -- Age Range
    if age and age != "None":
        user.age_range = age.strip()
        user.last_updated["age_range"] = str(datetime.utcnow())

    # -- Story Preference
    if story_pref is not None and story_pref != "None":
        user.story_pref = bool(story_pref)
        user.last_updated["story_pref"] = str(datetime.utcnow())

    # -- Playtime
    if playtime and playtime != "None":
        user.playtime = playtime.strip().lower()
        user.last_updated["playtime"] = str(datetime.utcnow())

    # -- Reject Tags (Genre vs Platform)
    if isinstance(reject_tags, list):
        print(f"[🛑 Raw reject_tags]: {reject_tags}")

        # Ensure proper structure
        if not isinstance(user.reject_tags, dict):
            user.reject_tags = {}

        user.reject_tags.setdefault("genre", [])
        user.reject_tags.setdefault("platform", [])
        user.reject_tags.setdefault("other", [])
        for tag in reject_tags:
            tag_clean = tag.strip().lower()

            # Try platform match
            matched_platform = get_best_platform_match(user_input=tag_clean, db=db)
            if matched_platform:
                if matched_platform not in user.reject_tags["platform"]:
                    user.reject_tags["platform"].append(matched_platform)
                print(f"✅ Platform matched: {tag_clean} → {matched_platform}")
                continue

            # Try genre match
            matched_genre = get_best_genre_match(input_genre=tag_clean, db=db)
            if matched_genre:
                if matched_genre not in user.reject_tags["genre"]:
                    user.reject_tags["genre"].append(matched_genre)
                print(f"✅ Genre matched: {tag_clean} → {matched_genre}")
                continue

            # If no match, store in "other"
            if tag_clean not in user.reject_tags["other"]:
                user.reject_tags["other"].append(tag_clean)
                print(f"⚠️ No match found for: {tag_clean} → added to 'other'")

        user.last_updated["reject_tags"] = str(datetime.utcnow())

    update_game_feedback_from_json(db=db, user_id=user.user_id, feedback_data=game_feedback)

    user.last_updated["game_feedback"] = str(datetime.utcnow())

    db.commit()


# ✅ Use OpenAI to classify mood, vibe, genre, and platform from free text
def classify_user_input(session, user_input: str) -> dict | str:
    # Get the last message from Thrum to include as context
    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    last_thrum_reply = thrum_interactions[-1].content if thrum_interactions else ""
    last_game = session.game_recommendations[-1].game if session.game_recommendations else None

    system_prompt = '''
You are a classification engine inside a mood-based game recommendation bot.

Your job is to extract and return the following user profile fields based on the user's input message.  
You must infer from both keywords and tone — even if the user is casual, brief, or vague. Extract even subtle clues.

---

🎯 FIELDS TO EXTRACT:

1. name (string)  
   → The user's first name. e.g., “I'm Alex” → "Alex".  
   → If not mentioned, return "None".

2. mood (string)  
   → Emotion or energy. e.g., relaxed, excited, tired, focused, bored, sad, hyped.  
   → Use tone, emojis, or even context like “long day” → “tired”.  
   → If unsure, return "None".

3. game_vibe (string)  
   → How the game should feel: relaxing, intense, wholesome, adventurous, spooky, cheerful, emotional, mysterious, dark, fast-paced, thoughtful.

4. genre (string)  
   → e.g., puzzle, horror, racing, shooter, strategy, farming, simulation, narrative, platformer.  
   → Accept synonyms like “scary” = horror, “farming sim” = farming.

5. platform_pref (string)  
   → PC, mobile, Xbox, PlayStation, Switch, etc.  
   → Detect implied platforms too: “on the train” = mobile, “on my couch” = console.

6. region (string)  
   → Location like India, US, UK, etc.  
   → Phrases like “I'm in Canada” → "Canada", “I'm from the UK” → "UK".

7. age (string)  
   → extract age as single number not a range. like 18, 25, 30, 50, etc.
   → from input e.g., "teen", "18-25", "30s", "50+".  
   → If mentioned or implied (e.g., “my kids” = likely 30s+), extract.

8. story_pref (boolean)  
   → True if they like games with story. False if they avoid it.  
   → “I want something with a good story” = True.  
   → “I skip cutscenes” = False.  
   → If unclear, return null.

9. playtime_pref (string)(** strict rule**)
   → if the user input is like user not like the recommended game then 
   → When they usually play: evenings, weekends, mornings, after work, before bed, “in short breaks”.  
   → Detect direct and subtle mentions.  
     Examples:
     - “Usually in the evenings” → "evenings"  
     - “Weekend gamer” → "weekends"  
     - “On the train” → "commute"  
     - “Before bed” → "night"

10. regect_tag (list of strings)  
   → What they dislike. Genres, moods, mechanics, or platforms.  
   → e.g., ["horror", "mobile", "realistic"]  
   → Hints: “I don't like shooters”, “not into mobile games”, “too realistic”.

11. game_feedback (list of dicts)  (** strict rule**)
   → if from the user input it is concluded that user does not like the recommended game (just for an example. if user input is "i don't like that" and you infere they actually don't like that game)then in game put the title from the last recommended game, accepted as False, and reason as the reason why they do not like it.
    if from the user input it is concluded that user like the recommended game (just for an example. if user input is "yeah i like that" and you infere they actually like that game)then in game put the title from the last recommended game, accepted as True, and reason as the reason why they like it.
   → If they like the game, put accepted as True and reason as why they like it
   → If they react to specific games with name they mentioned in user input(just for an example. if user input is "i love Celeste" and you infere they actually like that game),then put that title in game, accepted as True or False based on their reaction, and reason as the reason why they like or dislike it.
   → If they react to specific games with like/dislike:
   [
     {
       "game": "Celeste",
       "accepted": false,
       "reason": "too intense for me"
     },
     {
       "game": "Unpacking",
       "accepted": true,
       "reason": "emotional and relaxing"
     }
   ]

---

🧠 RULES:
- If a field cannot be inferred, return "None" (or [] for lists, null for booleans).
- DO NOT include any explanation.
- Always return strictly valid JSON.

🛠️ OUTPUT FORMAT (Strict JSON):

{
  "name": "...",
  "mood": "...",
  "game_vibe": "...",
  "genre": "...",
  "platform_pref": "...",
  "region": "...",
  "age": "...",
  "story_pref": true/false,
  "playtime_pref": "...",
  "regect_tag": ["..."],
  "game_feedback": [
    {
      "game": "...",
      "accepted": true/false/None,
      "reason": "..."
    }
  ]
}

🧠 HINTS:
- If a field is not mentioned or cannot be inferred, return "None" (or [] for lists).
- Do NOT add extra text or explanation — just return the clean JSON.
'''

    # Compose user prompt
    user_prompt = f'''
Previous bot message:
Thrum: "{last_thrum_reply}"

User reply:
"{user_input}"

last recommended game:
"{last_game}"

- classify based on user's reply and thrum's message (undersand it deeply waht they want to say.)
Now classify into the format below.
'''

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()}
            ],
            temperature=0
        )

        # Try parsing the LLM output into JSON
        try:
            result = json.loads(response.choices[0].message.content)
        except Exception:
            result = {
                "name": "None",
                "mood": "None",
                "game_vibe": "None",
                "genre": "None",
                "platform_pref": "None",
                "region": "None",
                "age": "None",
                "story_pref": None,
                "playtime_pref": "None",
                "regect_tag": [],
                "game_feedback": []
            }

        print(f"[🧠 Classification Result-------------]: {result}")
        return result

    except OpenAIError as e:
        print(f"⚠️ OpenAI Error: {e}")
        return "⚠️ Something went wrong. Please try again."
    
async def have_to_recommend(db: Session, user, classification: dict, session) -> bool:
    print(f"call have_to_recommend")
    # Retrieve the last game recommendation for the user in the current session
    last_rec = db.query(GameRecommendation).filter(
        GameRecommendation.user_id == user.user_id,
        GameRecommendation.session_id == session.session_id
    ).order_by(GameRecommendation.timestamp.desc()).first()
    print(f"last_rec : {last_rec}")
    # If no previous recommendation exists, return True (new recommendation needed)
    if not last_rec:
        return True
    
    # Extract the user's current preferences from the classification dictionary
    user_genre = classification.get('genre', None)
    user_mood = classification.get('mood', None)
    user_platform = classification.get('platform_pref', None)
    user_reject_tags = classification.get('regect_tag', [])
    user_game_feedback = classification.get("game_feedback", [])

    # Extract the preferences of the last recommended game
    today = datetime.utcnow().date().isoformat()
    last_rec_mood = user.mood_tags.get(today)
    last_rec_genre = last_rec.game.genre if last_rec.game else None
    last_rec_platforms = [gp.platform for gp in last_rec.game.platforms] if last_rec.game else []  # Platforms from GamePlatform table
    last_rec_reject_tags = user.reject_tags.get("genre", [])  # Extracted from the user's reject tags

    # Fetch the genre preferences from the user's profile (UserProfile table)
    user_profile_genre = user.genre_prefs.get(today, []) if user.genre_prefs else []
    print(f"user_profile_genre : {user_profile_genre}")
    user_profile_platform = user.platform_prefs.get(today, []) if user.platform_prefs else []

    print(f"user_profile_platform : {user_profile_platform}")

    # Check if the genre in classification matches the user's profile genre
    if user_genre:
        # Check if any genre in user_profile_genre matches the genres in last_rec_genre
        if user_profile_genre and not any(user_genre.lower() in genre.lower() for genre in last_rec_genre):
            print(f"genre")
            last_rec.accepted = False
            last_rec.reason = f"likes specific {user_genre} games"
            db.commit()
            return True  # Genre mismatch, new recommendation needed
    
    # Check if the mood in classification matches the user's last mood
    if user_mood:
        today = datetime.utcnow().date().isoformat()
        if user.mood_tags.get(today) != last_rec_mood:
            print(f"mood")
            last_rec.accepted = False
            last_rec.reason = f"want game of specific {user_mood}"
            db.commit()
            return True  # Mood mismatch, new recommendation needed

    # Check if the platform preference matches any of the platforms in last_rec_platforms
    if user_platform:
        if user_profile_platform and not any(p.lower() in [lp.lower() for lp in last_rec_platforms] for p in user_profile_platform):
            print("user_platform")
            last_rec.accepted = False
            last_rec.reason = f"want {user_platform} games but this is not in that platform"
            db.commit()
            return True  # Platform mismatch

    # Check for reject tag mismatches
    print(f'user_reject_tags : {user_reject_tags}')
    # Flatten all tags from user.reject_tags across all categories
    user_reject_genres = user.reject_tags.get("genre", []) if user.reject_tags else []
    last_genre_reject_tag = user_reject_genres[-1] if user_reject_genres else None

    if last_genre_reject_tag and last_rec_genre:
        if any(last_genre_reject_tag.lower() == genre.lower() for genre in last_rec_genre):
            print(f"❌ Last rejected genre '{last_genre_reject_tag}' is present in game's genre: {last_rec_genre}")
            last_rec.accepted = False
            last_rec.reason = f"user recently rejected genre: {last_genre_reject_tag}"
            db.commit()
            return True

    # Loop through feedbacks and update last_rec if any are negative
    for fb in user_game_feedback:
        if isinstance(fb, dict) and fb.get("accepted") is False:
            print("🛑 Feedback: user rejected a game")
            return True  # Trigger new recommendation

    return False  # No new recommendation needed, preferences match