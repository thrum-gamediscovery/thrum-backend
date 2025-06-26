from datetime import datetime, timedelta
from sqlalchemy.orm import Session as DBSession
from app.db.models.session import Session
from app.db.models.enums import SessionTypeEnum

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
def update_or_create_session(db: DBSession, user):
    now = datetime.utcnow()
    last_session = (
        db.query(Session)
        .filter(Session.user_id == user.user_id)
        .order_by(Session.start_time.desc())
        .first()
    )

    if not last_session:
        # First-time user
        new_session = Session(
            user_id=user.user_id,
            start_time=now,
            end_time=now,
            state=SessionTypeEnum.ONBOARDING
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session

    last_active_time = last_session.end_time or last_session.start_time
    elapsed = now - last_active_time

    # 📝 Update last session state
    if elapsed > timedelta(hours=48):
        last_session.state = SessionTypeEnum.COLD
    elif elapsed > timedelta(hours=11):
        last_session.state = SessionTypeEnum.PASSIVE
    else:
        last_session.state = SessionTypeEnum.ACTIVE
        last_session.end_time = now  # Extend active session

    db.commit()

    # 🚀 Start a new session if user was passive or cold
    if last_session.state in [SessionTypeEnum.PASSIVE, SessionTypeEnum.COLD]:
        new_session = Session(
            user_id=user.user_id,
            start_time=now,
            end_time=now,
            state=SessionTypeEnum.ONBOARDING
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session

    return last_session

# 🎭 Detect mood shifts and start new session if mood changed
def update_or_create_session_mood(db: DBSession, user, new_mood: str) -> Session:
    now = datetime.utcnow()
    last_session = (
        db.query(Session)
        .filter(Session.user_id == user.user_id)
        .order_by(Session.start_time.desc())
        .first()
    )

    if not last_session:
        # No session exists — first one
        session = Session(
            user_id=user.user_id,
            start_time=now,
            end_time=now,
            entry_mood=new_mood,
            exit_mood=new_mood
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    if last_session.exit_mood == new_mood:
        # Mood unchanged — just update timestamp
        last_session.exit_mood = new_mood
        db.commit()
        return last_session

    # Mood changed — close current session and create new one
    last_session.exit_mood = new_mood
    db.commit()

    new_session = Session(
        user_id=user.user_id,
        start_time=now,
        entry_mood=new_mood,
        exit_mood=new_mood
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session
