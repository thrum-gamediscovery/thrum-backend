from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException
from app.db.session import SessionLocal
from app.db.models.session import Session
from app.db.models.enums import SessionTypeEnum
from app.services.session_manager import get_session_state
from datetime import datetime

from starlette.responses import JSONResponse

class SessionIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        db = SessionLocal()
        try:
            if request.url.path in ["/docs", "/openapi.json", "/api/v1/whatsapp/webhook"]:
                return await call_next(request)

            raw_user_id = request.headers.get("X-User-ID")
            if not raw_user_id:
                return JSONResponse(status_code=400, content={"detail": "Missing X-User-ID header"})

            user_id = raw_user_id.split(",")[0].strip()

            last_session = (
                db.query(Session)
                .filter(Session.user_id == user_id)
                .order_by(Session.start_time.desc())
                .first()
            )

            if last_session:
                last_active = last_session.end_time or last_session.start_time
                new_state = get_session_state(last_active)
                last_session.state = new_state
                last_session.end_time = datetime.utcnow()
                db.commit()
                request.state.session_id = last_session.session_id
            else:
                new_session = Session(
                    user_id=user_id,
                    start_time=datetime.utcnow(),
                    state=SessionTypeEnum.ONBOARDING
                )
                db.add(new_session)
                db.commit()
                db.refresh(new_session)
                request.state.session_id = new_session.session_id

            response = await call_next(request)
            return response
        finally:
            db.close()