from datetime import datetime, timedelta
from sqlalchemy.orm import Session as DBSession
from app.db.models.session import Session
from app.db.models.enums import SessionTypeEnum
from app.services.nudge_checker import detect_user_is_cold  # ✅ import smart tone checker

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
        new_session = Session(
            user_id=user.user_id,
            start_time=now,
            end_time=now,
            state=SessionTypeEnum.ONBOARDING,
            meta_data={"is_user_cold": False}
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session

    # ✅ Detect if user is cold based on interaction pattern
    is_cold = detect_user_is_cold(last_session, db)
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
            meta_data={"is_user_cold": is_cold}
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session

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
