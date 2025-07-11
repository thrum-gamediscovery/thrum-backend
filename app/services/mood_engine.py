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

# SECTION 1 - MOOD & INPUT CLASSIFIER PHASE
async def classify_entry(db, user, session, input_text: str) -> dict:
    from app.services.tone_classifier import classify_tone
    print(f"📥 Entry message: {input_text}")

    # Step 1: Detect mood
    mood = await detect_mood_from_text(db=db, user_input=input_text)
    print(f"🧠 Detected mood: {mood}")

    # Step 2: Classify tone
    tone = classify_tone(input_text)
    print(f"🎭 Classified tone: {tone}")

    # Step 3: Confidence score
    vec = model.encode(input_text, convert_to_tensor=True)
    norm = np.linalg.norm(vec.cpu().numpy())
    confidence_score = round(min(1.0, norm / 10), 3)
    print(f"🔍 Confidence score: {confidence_score}")

    # Step 4: Save into session
    session.entry_mood = mood
    session.meta_data = session.meta_data or {}
    session.meta_data["entry_tone"] = tone
    session.meta_data["confidence_score"] = confidence_score

    # Step 5: Save into user for today
    from datetime import datetime
    from sqlalchemy.orm.attributes import flag_modified
    today = str(datetime.utcnow().date())
    user.mood_tags[today] = mood
    user.last_updated["mood_tags"] = str(datetime.utcnow())
    flag_modified(user, "mood_tags")
    flag_modified(user, "last_updated")

    db.commit()

    return {
        "mood": mood,
        "tone": tone,
        "confidence_score": confidence_score
    }