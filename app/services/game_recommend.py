# Import required modules
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from app.db.models.mood_cluster import MoodCluster
from app.db.models.game_platforms import GamePlatform
from app.db.models.game import Game
from sqlalchemy import func
from scipy.spatial.distance import cosine
from typing import Optional, Tuple, Dict

# Load the MiniLM model for embedding generation
model = SentenceTransformer("all-MiniLM-L12-v2")

# Main function to recommend a game based on user's mood, vibe, genre, and platform
def game_recommendation(db: Session, user) -> Tuple[Optional[Dict], Optional[str]]:
    # Step 1: Extract latest user mood, vibe, genre, and platform
    mood = list(user.mood_history.values())[-1] if user.mood_history else None
    vibe = list(user.game_vibe.values())[-1] if user.game_vibe else None
    genre = user.genre_interest.get("likes")[0] if user.genre_interest and user.genre_interest.get("likes") else None
    platform = user.platform_preference

    # Return early if any required user field is missing
    if not (mood and vibe and genre and platform):
        print("Missing required user fields.")
        return None, None

    # Step 2: Retrieve mood cluster tags for filtering
    mood_entry = db.query(MoodCluster).filter(MoodCluster.mood == mood).first()
    if not mood_entry or not mood_entry.game_tags:
        print(f"No game tags found for mood: {mood}")
        return None, None
    cluster_tags = mood_entry.game_tags

    # Step 3: Get game IDs for the specified platform (case-insensitive match)
    game_ids = db.query(GamePlatform.game_id).filter(
        GamePlatform.platform.ilike(f"%{platform}%")
    ).subquery()

    # Query games that match platform, mood cluster, and have embeddings
    candidate_games = db.query(Game).filter(
        Game.game_id.in_(game_ids),
        func.json_extract_path_text(Game.mood_tags, 'cluster').in_(cluster_tags),
        Game.mood_embedding.isnot(None),
        Game.game_embedding.isnot(None)
    ).all()

    # Return if no candidate games found
    if not candidate_games:
        print("No candidate games matched all filters.")
        return None, None

    # Step 4: Compute similarity between user input and game embeddings
    mood_vector = model.encode(f"{mood} {vibe}")
    genre_vector = model.encode(f"{vibe} {genre}")

    ranked = []
    for game in candidate_games:
        mood_sim = 1 - cosine(mood_vector, game.mood_embedding)
        content_sim = 1 - cosine(genre_vector, game.game_embedding)
        final_score = 0.5 * mood_sim + 0.5 * content_sim  # weighted average
        ranked.append((game, final_score))

    # Sort games by final similarity score in descending order
    ranked.sort(key=lambda x: x[1], reverse=True)

    # Step 5: Return top-ranked game as JSON (title, genre, short description)
    if ranked:
        top_game = ranked[0][0]
        return {
            "title": top_game.title,
            "genre": top_game.genre,
            "description": top_game.description[:200] if top_game.description else None
        }, None
    else:
        return None, None
