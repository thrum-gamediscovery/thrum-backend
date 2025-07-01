import openai
import os
import json
from openai import OpenAIError
from datetime import date, datetime
from sqlalchemy.orm import Session
from app.db.models.enums import SenderEnum
from app.db.models.session import Session
from app.db.models.game_recommendations import GameRecommendation

openai.api_key = os.getenv("OPENAI_API_KEY")


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
   → only add anything in regected_tag if it is sure otherwise not

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

- classify based on user's reply and thrum's message (undersand it deeply what they want to say.)
- 
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

    # Loop through feedbacks and update last_rec if any are negative
    for fb in user_game_feedback:
        if isinstance(fb, dict) and fb.get("accepted") is False:
            print("🛑 Feedback: user rejected a game")
            return True  # Trigger new recommendation
        
    # Check if the genre in classification matches the user's profile genre
    if user_genre and user_genre is not None:
        print(f"user's genre : {user_genre}")
        # Check if any genre in user_profile_genre matches the genres in last_rec_genre
        if user_profile_genre and not any(user_profile_genre[-1].lower() in genre.lower() for genre in last_rec_genre):
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

    return False  # No new recommendation needed, preferences match