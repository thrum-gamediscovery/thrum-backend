import pandas as pd
import ast
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..app.db.models.mood_cluster import MoodCluster  # Adjust import as needed
from ..app.core.config import settings

# Step 1: Load CSV
df = pd.read_csv("./mood_with_embeddings.csv")

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

# Step 3: Add data to DB
for _, row in df.iterrows():
    mood = row['mood']
    
    # Parse game_tags safely
    if isinstance(row['game_tags'], str):
        game_tags = parse_game_tags(row['game_tags'])
    else:
        game_tags = []

    # Parse embedding
    embedding = ast.literal_eval(row['embedding']) if isinstance(row['embedding'], str) else row['embedding']

    # Create and add to session
    cluster = MoodCluster(mood=mood, game_tags=game_tags, embedding=embedding)
    session.merge(cluster)  # merge handles insert/update
    print(f"Added: {mood}")
    print(game_tags)

# Step 4: Commit
session.commit()
session.close()
