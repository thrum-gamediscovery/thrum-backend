from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from app.db.models.mood_cluster import MoodCluster
from app.db.models.game_platforms import GamePlatform
from app.db.models.game_recommendations import GameRecommendation
from app.db.models.session import Session as UserSession
from app.db.models.game import Game
from sqlalchemy import func
from scipy.spatial.distance import cosine
from datetime import datetime
from typing import Optional, Dict, Tuple

model = SentenceTransformer("all-MiniLM-L12-v2")

def game_recommendation(db: Session, user, session) -> Optional[Tuple[Dict, None]]:
    today = datetime.utcnow().date().isoformat()

    # Extract today’s genre, platform, mood
    mood = user.mood_tags.get(today) if user.mood_tags and today in user.mood_tags else None
    genre_list = user.genre_prefs.get(today, []) if user.genre_prefs else []
    genre = genre_list[-1] if genre_list else None
    platform_list = user.platform_prefs.get(today, []) if user.platform_prefs else []
    platform = platform_list[-1] if platform_list else None
    print(f"Today's mood: {mood}, genre: {genre}, platform: {platform}")
    # Get cluster tags
    cluster_tags = []
    if mood:
        mood_entry = db.query(MoodCluster).filter(MoodCluster.mood == mood).first()
        if mood_entry and mood_entry.game_tags:
            cluster_tags = mood_entry.game_tags 

    # Get platform game_ids once
    platform_game_ids = []
    if platform:
        platform_game_ids = [row[0] for row in db.query(GamePlatform.game_id).filter(
            GamePlatform.platform.ilike(f"%{platform}%")
        ).all()]

    # Progressive filtering
    filter_levels = [
        {"genre": True, "platform": True, "cluster": True},
        {"genre": True, "platform": True, "cluster": False},
        {"genre": True, "platform": False, "cluster": False},
        {"genre": False, "platform": False, "cluster": False}
    ]

    candidate_games = []

    for level in filter_levels:
        query = db.query(Game)

        if level["genre"] and genre:
            query = query.filter(Game.genre.any(genre.lower()))

        if level["platform"] and platform and platform_game_ids:
            query = query.filter(Game.game_id.in_(platform_game_ids))

        if level["cluster"] and cluster_tags:
            query = query.filter(
                func.json_extract_path_text(Game.mood_tags, 'cluster').in_(cluster_tags)
            )

        query = query.filter(
            Game.mood_embedding.isnot(None),
            Game.game_embedding.isnot(None)
        )

        candidate_games = query.all()

        # Apply dislikes / reject_tags
        disliked_ids = set(user.dislikes.get("dislike", [])) if user.dislikes else set()
        rejected_genres = set(user.reject_tags.get("genre", [])) if user.reject_tags else set()

        filtered_games = []
        for game in candidate_games:
            if str(game.game_id) in disliked_ids:
                continue
            if any(g.lower() in rejected_genres for g in (game.genre or [])):
                continue
            filtered_games.append(game)

        if filtered_games:
            print(f"✅ Found {len(filtered_games)} candidates after level {filter_levels.index(level) + 1} filters.")
            break
        
    if not filtered_games:
        print("❌ All games rejected by user prefs.")
        return None, None

    # Ranking
    mood_vector = model.encode(mood) if mood else None
    genre_vector = model.encode(genre) if genre else None

    def compute_score(game: Game):
        mood_sim = 0
        genre_sim = 0
        mood_weight = 0.6 if mood_vector is not None else 0
        genre_weight = 0.4 if genre_vector is not None else 0

        if mood_vector is not None:
            mood_sim = 1 - cosine(mood_vector, game.mood_embedding)
        if genre_vector is not None:
            genre_sim = 1 - cosine(genre_vector, game.game_embedding)

        if mood_weight + genre_weight == 0:
            return 0.01
        return (mood_weight * mood_sim) + (genre_weight * genre_sim)

    ranked = [(g, compute_score(g)) for g in filtered_games]
    ranked.sort(key=lambda x: x[1], reverse=True)
    top_game = ranked[0][0]

    print(f"Top game recommendation: {top_game.title} (score: {ranked[0][1]:.4f})")

    # Platforms
    platforms = db.query(GamePlatform.platform).filter(
        GamePlatform.game_id == top_game.game_id
    ).all()
    platform_list = [p[0] for p in platforms]
    
    print(f"Platforms for {top_game.title}: {platform_list}")
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
        "platforms": platform_list
    }, None