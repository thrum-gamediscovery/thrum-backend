
from datetime import datetime, timedelta
from sqlalchemy.orm import Session as DBSession
from app.db.models.session import Session
from app.db.models.enums import SessionTypeEnum

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

def update_or_create_session(db: DBSession, user):
    last_session = (
        db.query(Session)
        .filter(Session.user_id == user.user_id)
        .order_by(Session.start_time.desc())
        .first()
    )

    if last_session:
        last_session.state = get_session_state(last_session.end_time or last_session.start_time)
        last_session.end_time = datetime.utcnow()
        db.commit()
        return last_session
    else:
        new_session = Session(
            user_id=user.user_id,
            start_time=datetime.utcnow(),
            state=SessionTypeEnum.ONBOARDING
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session
