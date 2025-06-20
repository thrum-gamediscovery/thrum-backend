# 📄 File: app/services/input_classifier.py

# Import required modules
import openai
import os
from openai import OpenAIError  # for
from datetime import date
from sqlalchemy.orm import Session
from app.services.mood_engine import detect_mood_from_text
from app.utils.genre import get_best_genre_match
from app.utils.platform_utils import get_best_platform_match

# Set OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")  # Set your key or replace this line with direct key for testing

# ✅ Update user profile with parsed classification fields
def update_user_from_classification(db: Session, user, user_input: str, classification: dict):
    platform = classification.get("platform")
    genre = classification.get("genre")
    mood = classification.get("mood")
    game_vibe = classification.get("game_vibe")

    # ✅ Update platform if available and valid
    if platform and platform != "None":
        user.platform_preference = get_best_platform_match(platform)

    # ✅ Update genre list if matched and not already present
    if genre and genre != "None":
        matched_genre = get_best_genre_match(genre)
        if matched_genre:
            current_genres = user.genre_interest.get("likes", [])
            if matched_genre not in current_genres:
                current_genres.append(matched_genre)
                user.genre_interest["likes"] = current_genres
        else:
            print(f":warning: Could not match genre: {genre}")

    # ✅ Detect and store today's mood from input
    if mood and mood != "None":
        today = date.today().isoformat()
        mood = detect_mood_from_text(db=db, user_input=mood)
        user.mood_history[today] = mood

    # ✅ Append new vibe to game_vibe if not already stored
    if game_vibe and game_vibe != "None":
        current_vibe = user.game_vibe.get("vibes", [])
        if game_vibe not in current_vibe:
            current_vibe.append(game_vibe)
            user.game_vibe["vibes"] = current_vibe

# ✅ Use OpenAI to classify mood, vibe, genre, and platform from free text
def classify_user_input(user_input: str) -> dict | str:
    prompt = f'''
You're a classification engine inside a mood-based game recommendation bot.

🎯 Your job:
Extract four fields from this user input:
- Mood (emotional tone: happy, bored, tired, cozy)
- Game Vibe (game feel: relaxing, intense, adventurous, cozy, exciting)
- Genre (game type: driving, shooter, horror, puzzle, fighting)
- Platform (device: PC, PlayStation, Xbox, Android)

🧠 Guidelines:
- Mood = emotional state of the user (inferred if needed)
- Game Vibe = how the game should feel (use user's exact words like "adventurous", "cozy", "exciting")
- Genre = actual game category (e.g., "puzzle", "shooter", "driving")
- Platform = device or OS mentioned (e.g., "PC", "PS5", "Linux") if user say that any other platform.

⚠️ Rules:
- Mood may be inferred from tone or emoji.
- Game Vibe and Genre must use the user's exact words.
- If any value is missing or unclear, set it as "None".

📝 Format your response as JSON like this:
{{ 
  "input": "mood/game_vibe/genre/platform", 
  "mood": "...", 
  "game_vibe": "...", 
  "genre": "...", 
  "platform": "..." 
}}

User: "{user_input}"
'''
    try:
        # 🔍 Call OpenAI API with classification prompt
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        # 🧠 Parse response into JSON dict
        import json
        try:
            result = json.loads(response.choices[0].message.content)
        except Exception:
            result = {
                "input": "None",
                "mood": "None",
                "game_vibe": "None",
                "genre": "None",
                "platform": "None"
            }
        print(f'input result : {result}')
        return result

    # ⚠️ Handle OpenAI error gracefully
    except OpenAIError:
        return "⚠️ Something went wrong. Please try again."
