import pandas as pd
import ast
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.db.models.game import Game
from app.db.models.game_platforms import GamePlatform
from app.core.config import settings

# DB config
DATABASE_URL = settings.DATABASE_URL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()

# Load CSV
df = pd.read_csv("./games_with_embeddings.csv")

for _, row in df.iterrows():
    try:
        # Parse all fields
        genre = ast.literal_eval(row['genre']) if isinstance(row['genre'], str) else []
        game_vibes = ast.literal_eval(row['game_vibes']) if isinstance(row['game_vibes'], str) else []
        mood_tags = ast.literal_eval(row['mood_tags']) if isinstance(row['mood_tags'], str) else []
        game_embedding = ast.literal_eval(row['game_embedding']) if isinstance(row['game_embedding'], str) else []
        mood_embedding = ast.literal_eval(row['mood_embedding']) if isinstance(row['mood_embedding'], str) else []
        platforms = ast.literal_eval(row['platform']) if isinstance(row['platform'], str) else []

        # Create Game object
        game = Game(
            title=row['title'],
            description=row.get('description'),
            genre=genre,
            game_vibes=game_vibes,
            mechanics=row.get('mechanics'),
            visual_style=row.get('visual_style'),
            emotional_fit=row.get('emotional_fit'),
            mood_tags=mood_tags,
            game_embedding=game_embedding,
            mood_embedding=mood_embedding
        )

        session.add(game)
        session.flush()  # Assigns game_id

        # Add platforms
        for plat in platforms:
            gp = GamePlatform(game_id=game.game_id, platform=plat)
            session.add(gp)
            print(f"{game.title}  : {plat}")

        print(f"✅ Added game: {game.title}")

    except Exception as e:
        print(f"❌ Error processing row {row.get('title')}: {e}")

session.commit()
session.close()
