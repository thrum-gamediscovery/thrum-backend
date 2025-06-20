# Import dependencies
import openai
from sqlalchemy.orm import Session
from app.services.game_recommend import game_recommendation
import json
import os
from datetime import date
from openai import OpenAIError  # for general exception handling


# Set OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY") 

# ✅ Generate a friendly game suggestion reply or ask missing info
def generate_thrum_reply(db: Session, user, user_input: str) -> str:
    game = game_recommendation(db=db, user=user)
    if user and user.mood_history:
        try:
            mood_history_dict = user.mood_history  # already a dict
            print(f'moods history : {mood_history_dict}')
            today = date.today().isoformat()  # e.g., '2025-06-19'
            mood = mood_history_dict.get(today)
            print(f"today's mood : {mood}")
        except Exception as e:
            print(f"⚠️ Failed to get today's mood: {e}")
            mood = None
    else:
        mood = None

    # ✅ Safely parse last genre from JSON
    genre = None
    if user and user.genre_interest:
        try:
            genre_data = user.genre_interest
            likes = genre_data.get("likes", [])
            if likes:
                genre = likes[-1]  # take last genre
        except (ValueError, TypeError):
            genre = None
    print(f"genre : {genre}")

    game_vibe = None
    if user and user.game_vibe:
        try:
            vibe_data = user.game_vibe
            vibes = vibe_data.get("vibes", [])
            if vibes:
                game_vibe = vibes[-1]  # take last genre
        except (ValueError, TypeError):
            game_vibe = None
    print(f"game vibe : {game_vibe}")

    # ✅ Get platform preference
    platform = user.platform_preference if user else None
    print(f"platform : {platform}")

    # ✅ Recommend game only if all user fields are present
    if mood and game_vibe and genre and platform:
        game = game_recommendation(db=db, user=user)
    else:
        game = None
    print(f"game : {game}")

    # ✅ Identify which fields are missing vs filled
    known_fields = {
    "mood": bool(mood),
    "game vibe": bool(game_vibe),
    "genre": bool(genre),
    "platform": bool(platform)
}
    missing = [k for k, v in known_fields.items() if not v]
    filled = [k for k, v in known_fields.items() if v]

    # ✅ Create dynamic GPT prompt with mood, vibe, genre, platform, and game
    prompt = f"""
You're Thrum 🎮 — just a chill, friendly human texting your buddy on WhatsApp to help them find fun games.

Here’s what you know so far:
- Mood (emotional tone): {mood if mood else "None"}
- Game Vibe (game feel or atmosphere): {game_vibe if game_vibe else "None"}
- Genre (game type or category): {genre if genre else "None"}
- Platform (device used to play): {platform if platform else "None"}
- Recommended_Game: {game if game else "None"}
- Last user message: "{user_input if user_input else "None"}"

Fields already known: {", ".join(filled)}
Fields still missing: {", ".join(missing)}

🎮 If Recommended_Game is present:
- only recommend game which is in Recommended_Game variable dont made up game by yourself.
- Don’t ask any questions.
- Just send a short, friendly 1–2 line message suggesting the game.
- Highlight the game name and include platform + a fun reason it fits.

✨ Sample lines:
- “Okay, I’ve got a pick 🎯”
- “You’ll love this one 👀”
- “Try this out — perfect for your vibe 💯”

💬 Style rules:
- Max 2–3 lines per reply
- Use emojis
- Never stack multiple questions

🧠 Tone Guide:
- “tired” → soft and caring
- “hyped” → energetic and bold
- “bored” → curious and playful
- “cozy” → warm and calm
- “competitive” → confident and focused

🎯 Your goal:
Sound like a real friend — casual, warm, emoji-friendly. Never robotic.
Ask **only one thing at a time**, and always follow this exact order:
**mood → game vibe → genre → platform**

⚠️ DO NOT repeat questions for fields already filled.
DO NOT confuse:
- Mood = emotional tone (happy, tired, bored, hyped)
- Game vibe = feel of game (relaxing, intense, adventurous, cozy)
- Genre = type of game (driving, puzzle, shooter, horror)
- Platform = device (PC, PS5, Xbox, Android)

✅ Question examples (feel free to vary wording a bit):these are example question dont ask same question and dont include like (happy, bored, cozy?) make it human like 
- If mood is missing → “Hey, how are you feeling today? 😊 (happy, bored, cozy?)”
- If vibe is missing → “What kind of game vibe are you into right now? 🎮 (relaxing, intense, fantasy?)”
- If genre is missing → “What type of games do you like? 🎲 (shooters, puzzles, racers?)”
- If platform is missing → “Where do you usually play your games? 💻🎮 (PC, PS5, Xbox?)”

All questions should feel human, friendly, and low-pressure — like you're texting a buddy.
Ask clearly enough that the user knows **what kind of answer you want**, but never sound formal or robotic.

Return only a short reply — max 1–2 lines (under 12 words), unless recommending a game.
"""


    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You are..."},
                {"role": "user", "content": prompt}
            ]
        )
        return response['choices'][0]['message']['content']
    
    # ✅ Handle OpenAI rate limit fallback
    except OpenAIError:
        return "⚠️ Something went wrong. Please try again."
