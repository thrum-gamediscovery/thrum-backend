from datetime import datetime, timedelta
from sqlalchemy.orm import Session as DBSession
from app.db.models.session import Session
from app.db.models.enums import SessionTypeEnum
from app.services.tone_shift_detection import detect_user_is_cold  # ✅ import smart tone checker
from app.db.models.enums import SenderEnum
from sqlalchemy.orm.attributes import flag_modified

def update_returning_user_flag(session):
    last_interaction_str = session.meta_data.get("last_interaction")
    if last_interaction_str:
        try:
            last_interaction = datetime.fromisoformat(last_interaction_str)
            idle_seconds = (datetime.utcnow() - last_interaction).total_seconds()
            # Only set to True if idle > 30 min (1800 seconds)
            session.meta_data["returning_user"] = idle_seconds > 1800
        except Exception:
            session.meta_data["returning_user"] = False
    else:
        session.meta_data["returning_user"] = False

def is_session_idle(session, idle_minutes=10):
    if not session.interactions:
        return False
    last_time = session.interactions[-1].timestamp
    return (datetime.utcnow() - last_time) > timedelta(minutes=idle_minutes)

# 🧠 Decide session state based on last activity timestamp
def get_session_state(last_active: datetime) -> SessionTypeEnum:
    now = datetime.utcnow()
    if not last_active:
        return SessionTypeEnum.ONBOARDING
    elapsed = now - last_active
    if elapsed > timedelta(hours=48):
        return SessionTypeEnum.COLD
    elif elapsed > timedelta(hours=11):
        return SessionTypeEnum.PASSIVE
    else:
        return SessionTypeEnum.ACTIVE

# 🔁 Create or update session based on user activity
async def update_or_create_session(db: DBSession, user):
    now = datetime.utcnow()
    last_session = (
        db.query(Session)
        .filter(Session.user_id == user.user_id)
        .order_by(Session.start_time.desc())
        .first()
    )

    if not last_session:
        new_session = Session(
            user_id=user.user_id,
            start_time=now,
            end_time=now,
            state=SessionTypeEnum.ONBOARDING,
            meta_data={
                "is_user_cold": False,
                "last_interaction": datetime.utcnow().isoformat(),
                "returning_user": False
            }
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session

    # ✅ Detect if user is cold based on interaction pattern
    is_cold = await detect_user_is_cold(last_session, db)
    last_session.meta_data = last_session.meta_data or {}
    last_session.meta_data["is_user_cold"] = is_cold

    last_active_time = last_session.end_time or last_session.start_time
    elapsed = now - last_active_time

    # 📝 Update session state
    if elapsed > timedelta(hours=48):
        last_session.state = SessionTypeEnum.COLD
    elif elapsed > timedelta(hours=11):
        last_session.state = SessionTypeEnum.PASSIVE
    else:
        last_session.state = SessionTypeEnum.ACTIVE
        last_session.end_time = now

    db.commit()

    # 🚀 Start new session if cold/passive
    if last_session.state in [SessionTypeEnum.PASSIVE, SessionTypeEnum.COLD]:
        new_session = Session(
            user_id=user.user_id,
            start_time=now,
            end_time=now,
            state=SessionTypeEnum.ONBOARDING,
            meta_data={
                "is_user_cold": is_cold,
                "last_interaction": datetime.utcnow().isoformat(),
                "last_session_state": last_session.state.name,
                "returning_user": False
            }
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session

    # 💡 NEW: Time-based returning_user check (30+ min idle = reengagement)
    last_interaction_time_str = last_session.meta_data.get("last_interaction")
    if last_interaction_time_str:
        try:
            last_interaction_time = datetime.fromisoformat(last_interaction_time_str)
            idle_seconds = (now - last_interaction_time).total_seconds()
            if idle_seconds > 1800:  # 30 minutes
                last_session.meta_data["returning_user"] = True
        except Exception:
            pass  # Fallback in case of invalid format

    last_session.meta_data["last_interaction"] = datetime.utcnow().isoformat()
    # update_returning_user_flag(last_session)

    return last_session

# 🎭 Mood shift session handler
def update_or_create_session_mood(db: DBSession, user, new_mood: str) -> Session:
    now = datetime.utcnow()
    last_session = (
        db.query(Session)
        .filter(Session.user_id == user.user_id)
        .order_by(Session.start_time.desc())
        .first()
    )

    if not last_session:
        session = Session(
            user_id=user.user_id,
            start_time=now,
            end_time=now,
            entry_mood=new_mood,
            exit_mood=new_mood,
            meta_data={"is_user_cold": False}
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    if not last_session.entry_mood:
        last_session.entry_mood = new_mood
        last_session.exit_mood = new_mood
        db.commit()
        return last_session

    if last_session.exit_mood == new_mood:
        last_session.exit_mood = new_mood
        db.commit()
        return last_session

    last_session.exit_mood = new_mood
    db.commit()

    new_session = Session(
        user_id=user.user_id,
        start_time=now,
        entry_mood=new_mood,
        exit_mood=new_mood,
        meta_data={"is_user_cold": False}
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session

def is_session_idle_or_fading(session) -> bool:
    now = datetime.utcnow()
    last_time = session.end_time or session.start_time
    minutes_idle = (now - last_time).total_seconds() / 60

    # Smart idle threshold — adapt based on how many user replies exist
    reply_count = len([i for i in session.interactions if i.sender.name == "User"])
    idle_threshold = 3 if reply_count <= 2 else 8

    if minutes_idle > idle_threshold:
        return True

    # Extra check: if is_user_cold is already flagged
    if session.meta_data.get("is_user_cold"):
        return True

    return False


# Example: group similar engaged tones together
ENGAGED_TONES = {"warm", "enthusiastic", "excited", "friendly", "playful", "curious", "cheerful", "encouraging"}
DISENGAGED_TONES = {"cold", "bored", "disengaged", "impatient", "dismissive", "sarcastic", "vague"}

async def tone_group(tone_tag: str) -> str:
    if tone_tag in ENGAGED_TONES:
        return "engaged"
    elif tone_tag in DISENGAGED_TONES:
        return "disengaged"
    else:
        return "neutral"

async def detect_tone_shift(session, window: int = 5, disengage_threshold: int = 2) -> bool:
    """
    Detects a meaningful negative tone shift in recent user messages.
    - window: How many recent user messages to check.
    - disengage_threshold: Minimum number of 'disengaged' tones required to trigger a flag.
    Returns True if a negative shift/disengagement is detected, else False.
    """
    if not hasattr(session, "interactions") or not session.interactions:
        return False

    # Get recent user interactions (latest first)
    user_interactions = [i for i in session.interactions[-window:] if getattr(i, "sender", None) == SenderEnum.User.value]
    if len(user_interactions) < 3:
        return False  # Not enough data

    # Map to tone groups
    tone_groups = [await tone_group(getattr(i, "tone_tag", "")) for i in user_interactions if getattr(i, "tone_tag", None)]

    # Count disengaged tones in the window
    disengaged_count = sum(1 for t in tone_groups if t == "disengaged")
    engaged_count = sum(1 for t in tone_groups if t == "engaged")

    # Rule: If at least `disengage_threshold` disengaged in recent window, and engaged is low, trigger shift
    if disengaged_count >= disengage_threshold and engaged_count < disengage_threshold:
        return True

    # Optional: Trigger if the most recent 2-3 user tones are all "disengaged"
    if tone_groups[-3:] == ["disengaged"] * 3:
        return True

    return False

def update_user_pacing(session):
    """
    Track user reply speed and determine pacing preference.
    Updates session.meta_data with pacing info.
    """
    if not session.interactions:
        return
    
    # Get user interactions only
    user_interactions = [i for i in session.interactions if i.sender == SenderEnum.User]
    if len(user_interactions) < 2:
        return
    
    # Calculate intervals between last 5 user messages
    recent_intervals = []
    for i in range(1, min(6, len(user_interactions))):
        current = user_interactions[-i]
        previous = user_interactions[-i-1]
        interval = (current.timestamp - previous.timestamp).total_seconds()
        recent_intervals.append(interval)
    
    if not recent_intervals:
        return
    
    # Calculate average reply interval
    avg_interval = sum(recent_intervals) / len(recent_intervals)
    
    # Determine pace
    if avg_interval < 5:  # Under 5 seconds = fast
        pace = "fast"
        style = "snappy"
    elif avg_interval > 30:  # Over 30 seconds = slow
        pace = "slow" 
        style = "gentle"
    else:
        pace = "medium"
        style = "balanced"
    
    # Update session metadata
    session.meta_data = session.meta_data or {}
    session.meta_data["reply_interval"] = avg_interval
    session.meta_data["pace"] = pace
    session.meta_data["style"] = style
    session.meta_data["message_count"] = session.meta_data.get("message_count", 0) + 1
    
    # Reset pacing every 10 messages or on tone shift
    if session.meta_data["message_count"] >= 10 or session.tone_shift_detected:
        session.meta_data["message_count"] = 0
        session.meta_data["pace_reset"] = True
        if session.tone_shift_detected:
            session.tone_shift_detected = False
    
    flag_modified(session, "meta_data")

def get_pacing_style(session):
    """
    Get current pacing style for prompt building.
    Returns tuple of (pace, style, length_hint)
    """
    if not session.meta_data:
        return "medium", "balanced", "normal"
    
    pace = session.meta_data.get("pace", "medium")
    style = session.meta_data.get("style", "balanced")
    
    # Length hints based on pace
    length_hints = {
        "fast": "short",
        "medium": "normal", 
        "slow": "detailed"
    }
    
    length_hint = length_hints.get(pace, "normal")
    return pace, style, length_hint

