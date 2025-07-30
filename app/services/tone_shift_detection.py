from datetime import datetime
from app.services.session_manager import detect_tone_shift
from sqlalchemy.orm.attributes import flag_modified

# Define dry reply patterns and low-confidence threshold
DRY_RESPONSE_KEYWORDS = ["meh", "whatever", "nah", "idk", "fine", "ok", "no"]
LOW_CONFIDENCE_THRESHOLD = 0.3

def is_dry_response(text: str) -> bool:
    return any(word in text.lower() for word in DRY_RESPONSE_KEYWORDS)


async def emotion_fusion(db, session, user):
    # 1. Detect tone via LLM or embedding
    last_tone_entry = session.meta_data.get("tone_history", [{}])[-1]
    tone = last_tone_entry.get("tone")
    tone_confidence = last_tone_entry.get("confidence", 0.5)

    # Returns {mood_result: mood_score} or None if not set
    today = datetime.utcnow().date().isoformat()
    today_mood = user.mood_tags.get(today, None)

    if today_mood:
        # There should be only one key-value pair, so you can unpack it
        mood_result, mood_confidence = next(iter(today_mood.items()))
    else:
        # Default fallback values
        mood_result, mood_confidence = None, 0.5
    
    # 3. Detect coldness / disengagement
    cold_shift = detect_tone_shift(session)
    
    # 4. Reconcile: prioritize strong/confident signals, resolve conflicts
    if tone_confidence < 0.5 and mood_confidence > 0.7:
        overall_emotion = mood_result
        emotion_source = "mood"
    elif cold_shift:
        overall_emotion = "disengaged"
        emotion_source = "cold_shift"
    elif tone_confidence >= mood_confidence:
        overall_emotion = tone
        emotion_source = "tone"
    else:
        overall_emotion = mood_result
        emotion_source = "mood"
    
    # 5. Bundle all for downstream
    fusion = {
        "tone": tone,
        "tone_confidence": tone_confidence,
        "mood": mood_result,
        "mood_confidence": mood_confidence,
        "cold_shift": cold_shift,
        "overall_emotion": overall_emotion,
        "emotion_source": emotion_source
    }
    # 6. Optionally: update session.meta_data and memory here
    session.meta_data["tone"] = tone
    session.meta_data["mood"] = mood_result
    session.meta_data["cold_shift"] = cold_shift
    session.meta_data["overall_emotion"] = overall_emotion
    flag_modified(session, "meta_data")
    db.commit()
    return fusion