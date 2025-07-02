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
    print(f"user input : {user_input}")
    
    # 🔍 Preprocess: lowercase word set for direct match
    input_words = set(word.lower() for word in user_input.split())

    # 🔍 Fetch all mood clusters from DB
    moods = db.query(MoodCluster).all()
    mood_names = [m.mood.lower() for m in moods]

    # 🔍 Step 1: Direct match with mood names
    for word in input_words:
        if word in mood_names:
            matched_mood = next((m.mood for m in moods if m.mood.lower() == word), None)
            print(f"⚡ Direct word match found: '{word}' → mood: {matched_mood}")
            return matched_mood

    # 🧠 Step 2: Fallback using cosine similarity with mood embeddings
    user_vector = embed_text(user_input)
    best_mood = None
    best_score = -1.0

    for mood in moods:
        mood_vector = mood.embedding
        if mood_vector is not None:
            sim = 1 - cosine(user_vector, mood_vector)
            print(f"{mood.mood} → cosine similarity: {sim:.4f}")
            if sim > best_score:
                best_score = sim
                best_mood = mood.mood

    # ✅ Return best matched mood based on similarity
    print(f"🧠 Best matched mood (fallback): {best_mood} (score: {best_score:.4f})")
    return best_mood
