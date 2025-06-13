
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db import models
from app.db.models.session import Session as GameSession
from datetime import datetime
import uuid
from app.db.models.enums import SessionTypeEnum

def seed_users(db: Session):
    if db.query(models.User).count() == 0:
        user = models.User(name="Alex", platform="Steam", phone_number="1234567890", genre_interest=["RPG", "Adventure"])
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✅ Seeded user: {user.name}")

def seed_games(db: Session):
    if db.query(models.Game).count() == 0:
        games = [
            models.Game(
                title="Hades",
                genre="Roguelike",
                platform="Steam",
                visual_style="Stylized",
                mechanics="Action",
                emotional_fit="intense",
                mood_tags=["fast-paced", "action"]
            ),
            models.Game(
                title="Stardew Valley",
                genre="Simulation",
                platform="Steam",
                visual_style="Pixel Art",
                mechanics="Farming",
                emotional_fit="cozy",
                mood_tags=["chill", "solo"]
            ),
            models.Game(
                title="Celeste",
                genre="Platformer",
                platform="Steam",
                visual_style="Pixel",
                mechanics="Precision Jumping",
                emotional_fit="emotional",
                mood_tags=["challenging", "solo", "emotional"]
            )
        ]
        db.add_all(games)
        db.commit()
        print(f"✅ Seeded {len(games)} games.")

def seed_session(db: Session, user):
    existing = db.query(GameSession).filter(GameSession.user_id == user.user_id).first()
    if not existing:
        session = GameSession(
            session_id=str(uuid.uuid4()),
            user_id=user.user_id,
            start_time=datetime.utcnow(),
            state=SessionTypeEnum.ONBOARDING
        )
        db.add(session)
        db.commit()
        print(f":white_check_mark: Seeded session for user {user.user_id} with state {session.state}")
    else:
        print(":information_source: Session already exists.")

def run_seed():
    db = SessionLocal()
    try:
        seed_users(db)
        seed_games(db)
        users = db.query(models.User).all()
        for user in users:
            seed_session(db, user)
    finally:
        db.close()