import pandas as pd
import ast
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models.mood_cluster import MoodCluster  # Adjust import as needed
from app.core.config import settings

# Step 1: Load CSV
df = pd.read_csv("./gameopedia/mood_with_embeddings.csv")

# Step 2: Setup DB connection (replace with your DB URI)
DATABASE_URL = settings.DATABASE_URL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()

import re

def parse_game_tags(raw):
    if not isinstance(raw, str):
        return []

    # Remove enclosing braces if present
    raw = raw.strip()
    if raw.startswith("{") and raw.endswith("}"):
        raw = raw[1:-1]

    # Split by comma, handle quoted multi-word strings and split them
    tags = []
    for token in raw.split(','):
        token = token.strip().strip('"').strip("'")
        if ' ' in token:
            tags.extend(token.split())  # split multi-word phrases
        else:
            tags.append(token)
    
    # Clean and deduplicate
    return list({tag.strip().lower() for tag in tags if tag})

def parse_game_vibe(raw):
    if not isinstance(raw, str):
        return []

    # Remove enclosing braces if present
    raw = raw.strip()
    if raw.startswith("{") and raw.endswith("}"):
        raw = raw[1:-1]

    # Split by comma, handle quoted multi-word strings and split them
    tags = []
    for token in raw.split(','):
        token = token.strip().strip('"').strip("'")
        if ' ' in token:
            tags.extend(token.split())  # split multi-word phrases
        else:
            tags.append(token)
    
    # Clean and deduplicate
    return list({tag.strip().lower() for tag in tags if tag})

# Step 3: Add data to DB
for _, row in df.iterrows():
    mood = row.get('mood')
    
    # Be sure to use the actual column names. Change 'game_tag' and 'game_vibe' as needed.
    game_tag_raw = row.get('game_tag', '') or row.get('game_tags', '')  # fallback if needed
    game_vibe_raw = row.get('game_vibe', '')

    game_tags = parse_game_tags(game_tag_raw) if isinstance(game_tag_raw, str) else []
    game_vibe = parse_game_vibe(game_vibe_raw) if isinstance(game_vibe_raw, str) else []

    # Parse embedding
    embedding = ast.literal_eval(row['embedding']) if isinstance(row['embedding'], str) else row['embedding']

    # Adjust constructor if your MoodCluster has more/other fields
    cluster = MoodCluster(
        mood=mood,
        game_tags=game_tags,
        game_vibe=game_vibe,  # If your model accepts game_vibes
        embedding=embedding
    )
    session.merge(cluster)  # merge handles upsert
    print(f"Added: {mood}")
    print(f"Game Tags: {game_tags}")
    print(f"Game Vibes: {game_vibe}")

session.commit()
session.close()
