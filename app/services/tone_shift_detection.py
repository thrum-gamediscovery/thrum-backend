import re
from sqlalchemy.orm import Session as DBSession
from app.db.models.session import Session as SessionModel
from app.db.models.enums import SenderEnum

# Define dry reply patterns and low-confidence threshold
DRY_RESPONSE_KEYWORDS = ["meh", "whatever", "nah", "idk", "fine", "ok", "no"]
LOW_CONFIDENCE_THRESHOLD = 0.3

def is_dry_response(text: str) -> bool:
    return any(word in text.lower() for word in DRY_RESPONSE_KEYWORDS)

def detect_tone_shift(session: SessionModel) -> bool:
    """
    Checks last 2–3 user messages to detect disengagement.
    Returns True if user seems cold.
    """
    recent_user_msgs = [i for i in session.interactions if i.sender == SenderEnum.User][-3:]
    dry_count = sum(1 for i in recent_user_msgs if is_dry_response(i.content))
    low_conf_count = sum(1 for i in recent_user_msgs if i.confidence_score is not None and i.confidence_score < LOW_CONFIDENCE_THRESHOLD)
    return dry_count >= 2 or low_conf_count >= 2

def mark_session_cold(db: DBSession, session: SessionModel):
    """
    Sets is_user_cold = True inside session.meta_data and commits.
    """
    session.meta_data = session.meta_data or {}
    session.meta_data["is_user_cold"] = True
    db.commit()
