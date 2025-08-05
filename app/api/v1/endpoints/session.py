"""
Handles session-related endpoints such as onboarding, idle reactivation, etc.
Session state logic will be managed here and refined in future.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession
from app.db.deps import get_db
from app.db.models.user_profile import UserProfile
from app.services.session_manager import update_or_create_session

router = APIRouter()

# 🚀 Starts or resumes a session for the given user
@router.post("/session/start")
async def start_session(user_id: str, db: DBSession = Depends(get_db)):
    # 🔍 Find user by user_id
    user = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not user:
        return {"error": "User not found"}

    # 🔁 Create new session or update existing one based on last activity
    session = update_or_create_session(db, user)

    # 📤 Return session details
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "state": session.state,
        "start_time": session.start_time,
        "end_time": session.end_time
    }

