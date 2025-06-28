from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from app.db.models.mood_cluster import MoodCluster
from app.db.models.game_platforms import GamePlatform
from app.db.models.game_recommendations import GameRecommendation
from app.db.models.session import Session as UserSession
from app.db.models.game import Game
from sqlalchemy import func, cast, Integer
from scipy.spatial.distance import cosine
from datetime import datetime
from typing import Optional, Dict, Tuple
from random import choice

model = SentenceTransformer("all-MiniLM-L12-v2")

def game_recommendation(db: Session, user, session) -> Optional[Tuple[Dict, bool]]:
    today = datetime.utcnow().date().isoformat()
    mood = user.mood_tags.get(today) if user.mood_tags and today in user.mood_tags else (
        next(reversed(user.mood_tags.values()), None) if user.mood_tags else None
    )
    genre = (
        user.genre_prefs.get(today, [])[-1] if user.genre_prefs and today in user.genre_prefs and user.genre_prefs[today]
        else next((g[-1] for g in reversed(user.genre_prefs.values()) if g), None) if user.genre_prefs else None
    )
    platform = (
        user.platform_prefs.get(today, [])[-1] if user.platform_prefs and today in user.platform_prefs and user.platform_prefs[today]
        else next((p[-1] for p in reversed(user.platform_prefs.values()) if p), None) if user.platform_prefs else None
    )
    print(f"Today's mood: {mood}, genre: {genre}, platform: {platform}")

    # Random fallback for cold start
    if not mood and not genre and not platform:
        print("No profile info — selecting safe random game.")
        random_game = db.query(Game).filter(
            Game.mood_embedding.isnot(None),
            Game.game_embedding.isnot(None),
            cast(Game.age_rating, Integer) < 18
        ).order_by(func.random()).first()
        if not random_game:
            return None, None

        platform_rows = db.query(GamePlatform.platform).filter(
            GamePlatform.game_id == random_game.game_id).all()
        return {
            "title": random_game.title,
            "genre": random_game.genre,
            "description": random_game.description[:200] if random_game.description else None,
            "platforms": [p[0] for p in platform_rows]
        }, False

    # Mood cluster expansion
    cluster_tags = []
    if mood:
        mood_entry = db.query(MoodCluster).filter(MoodCluster.mood == mood).first()
        if mood_entry and mood_entry.game_tags:
            cluster_tags = mood_entry.game_tags

    platform_game_ids = []
    if platform:
        platform_game_ids = [row[0] for row in db.query(GamePlatform.game_id).filter(
            GamePlatform.platform.ilike(f"%{platform}%")).all()]

    # Add story filter with fallback logic
    filter_levels = [
        {"genre": True, "platform": True, "cluster": True, "story": True},
        {"genre": True, "platform": True, "cluster": False, "story": True},
        {"genre": True, "platform": False, "cluster": False, "story": True},
        {"genre": True, "platform": True, "cluster": True, "story": False},
        {"genre": True, "platform": True, "cluster": False, "story": False},
        {"genre": True, "platform": False, "cluster": False, "story": False},
    ]

    candidate_games = []
    for level in filter_levels:
        query = db.query(Game)
        if level["genre"] and genre:
            query = query.filter(Game.genre.any(genre.lower()))
        if level["platform"] and platform and platform_game_ids:
            query = query.filter(Game.game_id.in_(platform_game_ids))
        if level["cluster"] and cluster_tags:
            query = query.filter(func.json_extract_path_text(Game.mood_tags, 'cluster').in_(cluster_tags))
        if level.get("story", False) and user.story_pref is not None:
            print(f"[🔍] Filtering by story preference: {user.story_pref}")
            query = query.filter(Game.has_story == user.story_pref)

        query = query.filter(Game.mood_embedding.isnot(None), Game.game_embedding.isnot(None))
        candidate_games = query.all()

        disliked_ids = set(user.dislikes.get("dislike", [])) if user.dislikes else set()
        rejected_genres = set(user.reject_tags.get("genre", [])) if user.reject_tags else set()

        filtered_games = []
        for game in candidate_games:
            if str(game.game_id) in disliked_ids:
                continue
            if any(g.lower() in rejected_genres for g in (game.genre or [])):
                continue
            filtered_games.append(game)
        print(f"[🔍] Filter level: genre={level['genre']}, platform={level['platform']}, cluster={level['cluster']}, story={level.get('story')}")
        print(f"[🎮] Games found: {len(filtered_games)}")
        if filtered_games:
            break

    if not filtered_games:
        return None, None

    mood_vector = model.encode(mood) if mood else None
    genre_vector = model.encode(genre) if genre else None

    def compute_score(game: Game):
        mood_sim = 0
        genre_sim = 0
        mood_weight = 0.6 if mood_vector is not None else 0
        genre_weight = 0.4 if genre_vector is not None else 0

        if mood_vector is not None and game.mood_embedding is not None:
            mood_sim = 1 - cosine(mood_vector, game.mood_embedding)
        if genre_vector is not None and game.game_embedding is not None:
            genre_sim = 1 - cosine(genre_vector, game.game_embedding)

        if mood_weight + genre_weight == 0:
            return 0.01
        return (mood_weight * mood_sim) + (genre_weight * genre_sim)

    ranked = sorted([(g, compute_score(g)) for g in filtered_games], key=lambda x: x[1], reverse=True)
    top_game = ranked[0][0]
    age_ask_required = False

    try:
        game_age = int(top_game.age_rating) if top_game.age_rating else None
    except ValueError:
        game_age = None

    if user.age_range:
        try:
            user_age = int(user.age_range)
        except ValueError:
            user_age = None
        if user_age is not None and game_age is not None and game_age > user_age:
            for g, _ in ranked[1:]:
                try:
                    alt_age = int(g.age_rating) if g.age_rating else None
                except ValueError:
                    alt_age = None
                if alt_age is None or alt_age <= user_age:
                    top_game = g
                    break
    else:
        if game_age is not None and game_age >= 18:
            age_ask_required = True

    platforms = db.query(GamePlatform.platform).filter(
        GamePlatform.game_id == top_game.game_id).all()

    game_rec = GameRecommendation(
        session_id=session.session_id,
        user_id=user.user_id,
        game_id=top_game.game_id,
        platform=platform,
        mood_tag=mood,
        accepted=None
    )
    db.add(game_rec)
    db.commit()

    return {
        "title": top_game.title,
        "genre": top_game.genre,
        "description": top_game.description[:200] if top_game.description else None,
        "platforms": [p[0] for p in platforms]
    }, age_ask_required