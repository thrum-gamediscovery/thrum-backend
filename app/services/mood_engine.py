# 📄 File: app/services/mood_engine.py

# Import required modules
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from app.db.models.mood_cluster import MoodCluster
import numpy as np
from typing import Optional
from scipy.spatial.distance import cosine

# ✅ Load MiniLM model globally to avoid repeated initialization
model = SentenceTransformer('all-MiniLM-L12-v2')

# ✅ Convert input text into embedding vector
async def embed_text(text: str) -> list[float]:
    return model.encode(text).tolist()

# ✅ Detect user mood from input text using keyword or embedding similarity
async def detect_mood_from_text(db: Session, user_input: str) -> Optional[str]:
    input_words = set(word.lower() for word in user_input.split())
    moods = db.query(MoodCluster).all()
    mood_names = [m.mood.lower() for m in moods]

    for word in input_words:
        if word in mood_names:
            matched_mood = next((m.mood for m in moods if m.mood.lower() == word), None)
            return matched_mood

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
    return best_mood