from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException
from app.db.session import SessionLocal
from app.db.models.session import Session
from app.db.models.enums import SessionTypeEnum
from app.services.session_manager import get_session_state
from datetime import datetime

class SessionIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        db = SessionLocal()
        try:
            raw_user_id = request.headers.get("X-User-ID")
            if not raw_user_id:
                raise HTTPException(status_code=400, detail="Missing X-User-ID header")

            if not raw_user_id:
                return await call_next(request)
            user_id = raw_user_id.split(",")[0].strip()
            # Find the latest session for this user
            last_session = (
                db.query(Session)
                .filter(Session.user_id == user_id)
                .order_by(Session.start_time.desc())
                .first()
            )
            if last_session:
                # Check session state based on last activity
                last_active = last_session.end_time or last_session.start_time
                new_state = get_session_state(last_active)
                last_session.state = new_state
                last_session.end_time = datetime.utcnow()
                db.commit()
                request.state.session_id = last_session.session_id
            else:
                # No session, create a new one
                new_session = Session(
                    user_id=user_id,
                    start_time=datetime.utcnow(),
                    state=SessionTypeEnum.ONBOARDING
                )
                db.add(new_session)
                db.commit()
                db.refresh(new_session)
                request.state.session_id = new_session.session_id
        finally:
            db.close()
        response = await call_next(request)
        return response