# 📄 File: app/services/mood_engine.py

# Import required modules
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session as DBSession
from app.db.models.mood_cluster import MoodCluster
import numpy as np
from typing import Optional
from scipy.spatial.distance import cosine

# ✅ Load MiniLM model globally to avoid repeated initialization
model = SentenceTransformer('all-MiniLM-L12-v2')

# ✅ Convert input text into embedding vector
async def embed_text(text: str) -> list[float]:
    return model.encode(text).tolist()

async def detect_mood_llm(user_input: str, client) -> Optional[str]:
    system_prompt = (
        "You are a mood detection assistant. Given a user's message, "
        "return a single word representing their current mood or emotional state. "
        "Examples: happy, sad, anxious, excited, relaxed, frustrated, neutral, etc. "
        "If the mood is unclear, reply only with: neutral."
    )
    user_prompt = f"User message: {user_input.strip()}\nMood:"
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0,
        )
        # Only take the first word, lowercase
        mood = response.choices[0].message.content.strip().split()[0].lower()
        return mood
    except Exception as e:
        return None

# ✅ Detect user mood from input text using keyword or embedding similarity
async def detect_mood_from_text(db: DBSession, user_input: str):
    input_words = set(word.lower() for word in user_input.split())
    moods = db.query(MoodCluster).all()
    mood_names = [m.mood.lower() for m in moods]

    for word in input_words:
        if word in mood_names:
            matched_mood = next((m.mood for m in moods if m.mood.lower() == word), None)
            return matched_mood, 0.95

    # ✅ Fix: Await the async embed_text call
    user_vector = await embed_text(user_input)
    user_vector = np.array(user_vector).flatten()

    best_mood = None
    best_score = -1.0

    for mood in moods:
        mood_vector = np.array(mood.embedding).flatten()
        if user_vector.shape != mood_vector.shape:
            print(f"⚠️ Skipping {mood.mood} due to shape mismatch.")
            continue

        sim = 1 - cosine(user_vector, mood_vector)
        if sim > best_score:
            best_score = sim
            best_mood = mood.mood

    print(f"🧠 Best matched mood (fallback): {best_mood} (score: {best_score:.4f})")
    return best_mood, best_score if best_mood is not None else ('Nuetral', 0.5)