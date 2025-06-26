from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException
from starlette.responses import Response
from app.db.session import SessionLocal
from app.db.models.session import Session
from app.db.models.enums import SessionTypeEnum
from app.services.session_manager import get_session_state
from datetime import datetime
from typing import Callable

class SessionIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        db = SessionLocal()
        try:
            # Skip session logic for public paths
            if request.url.path in ["/", "/docs", "/openapi.json", "/favicon.ico"] or not request.url.path.startswith("/api"):
                return await call_next(request)

            raw_user_id = request.headers.get("X-User-ID")
            if not raw_user_id:
                raise HTTPException(status_code=400, detail="Missing X-User-ID header")

            user_id = raw_user_id.split(",")[0].strip()

            # Find the latest session for this user
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

        finally:
            db.close()

        response = await call_next(request)
        return response
