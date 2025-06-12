"""
Handles session-related endpoints such as onboarding, idle reactivation, etc.

Session state logic will be managed here and refined in future.
"""


from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession
from app.db.deps import get_db
from app.db.models.user import User
from app.services.session_manager import update_or_create_session

router = APIRouter()

# This is a placeholder route for testing session creation/updating
@router.post("/session/start")
def start_session(user_id: str, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return {"error": "User not found"}

    session = update_or_create_session(db, user)
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "state": session.state,
        "start_time": session.start_time,
        "end_time": session.end_time
    }
