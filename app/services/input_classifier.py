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
        update_or_create_session_mood(db, user, new_mood=mood_result)

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

    if isinstance(game_feedback, list):
        for feedback in game_feedback:
            try:
                game_text = feedback.get("game", "").strip()
                accepted = feedback.get("accepted", True)
                reason = feedback.get("reason", "")

                game_id = resolve_game_id(db, game_text, user, session)
                if not game_id:
                    print(f"⚠️ Could not resolve game: '{game_text}'")
                    continue

                game_rec = GameRecommendation(
                    session_id=session.session_id,
                    user_id=user.user_id,
                    game_id=game_id,
                    platform=user.platform.name if user.platform else None,
                    mood_tag=mood_result if mood and mood != "None" else None,
                    accepted=accepted,
                    reason=reason
                )
                db.add(game_rec)

            except Exception as e:
                print(f"❌ Error saving feedback: {e}")
                continue

    user.last_updated["game_feedback"] = str(datetime.utcnow())

    db.commit()

# ✅ Use OpenAI to classify mood, vibe, genre, and platform from free text
def classify_user_input(session, user_input: str) -> dict | str:
    # Get the last message from Thrum to include as context
    thrum_interactions = [i for i in session.interactions if i.sender == SenderEnum.Thrum]
    last_thrum_reply = thrum_interactions[-1].content if thrum_interactions else ""

    system_prompt = '''
You are a classification engine inside a mood-based game recommendation bot.

Your job is to extract and return the following user profile fields based on the user's input message.  
You must infer from both keywords and tone — even if the user is casual or vague.

---

🎯 FIELDS TO EXTRACT:

1. name (string)  
   → The user's first name. e.g., “I’m Alex” → "Alex".  
   → If not mentioned, return "None".

2. mood (string)  
   → Emotion or energy. e.g., relaxed, excited, tired, focused.  
   → Use emojis or tone as hints. If unsure, return "None".

3. game_vibe (string)  
   → How the game should feel: relaxing, intense, wholesome, adventurous, spooky, cheerful, etc.

4. genre (string)  
   → e.g., puzzle, horror, racing, shooter, strategy, farming.

5. platform_pref (string)  
   → PC, mobile, Xbox, PlayStation, Switch, etc.

6. region (string)  
   → Location like India, US, UK. From phrases like “I’m in Canada.”

7. age (string)  
   → e.g., "teen", "18-25", "30s", "50+". Return if stated or implied.

8. story_pref (boolean)  
   → True if the user likes games with story. False if not. "None" if unclear.

9. playtime_pref (string)  
   → When they play: evenings, weekends, morning, “after work”.

10. regect_tag (list of strings)  
   → What they dislike. Genres or platforms. e.g., ["horror", "mobile", "realistic"]

11. game_feedback (list of dicts)  
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
- Do not include any extra explanation — return only the JSON object.

---

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

        print(f"[🧠 Classification Result]: {result}")
        return result

    except OpenAIError as e:
        print(f"⚠️ OpenAI Error: {e}")
        return "⚠️ Something went wrong. Please try again."