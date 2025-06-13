from fastapi import APIRouter, Form, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.db.models.user import User
from app.db.deps import get_db
from datetime import datetime
from app.db.models.enums import PlatformEnum

router = APIRouter()

@router.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(...),
    db: Session = Depends(get_db)
):
    print(f"Message from {From}: {Body}")
    user = db.query(User).filter(User.phone_number == From).first()

    # Step 1: New user — create profile
    if not user:
        user = User(
            phone_number=From,
            platform=PlatformEnum.WhatsApp,
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return "👋 Hi there! Welcome to Thrum (GameDive). What's your name?"

    # 2. Ask for name
    if user.phone_number == From:
        user.name = Body.strip()
        db.commit()
        return f"Nice to meet you, {user.name}! What kind of games do you enjoy? (e.g., puzzle, racing, RPG)"

    # 3. Ask for genre interest
    if not user.genre_interest or user.genre_interest == {}:
        genres = [g.strip().lower() for g in Body.split(",")]
        user.genre_interest = {"likes": genres}
        db.commit()
        return "Awesome! What’s your current mood? (e.g., bored, relaxed, excited)"

    # 4. Ask for mood
    if not user.mood_history or user.mood_history == {}:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        user.mood_history = {today: Body.strip().lower()}
        db.commit()
        return "✅ Got it! I’ll now start finding a game that matches your vibe. Just type 'suggest game'."

    # Already onboarded
    return "You're all set! Type 'suggest game' and I’ll recommend something cool. 🎮"
