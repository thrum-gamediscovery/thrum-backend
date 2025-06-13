
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db import models

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

def run_seed():
    db = SessionLocal()
    try:
        seed_users(db)
        seed_games(db)
    finally:
        db.close()

if __name__ == "__main__":
    run_seed()
