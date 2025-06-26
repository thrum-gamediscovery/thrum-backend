# 📁 app/services/game_selector.py

from sqlalchemy.orm import Session
from app.db.models.game import Game

def get_recommended_games(user, db: Session, top_k=5):
    mood = user.mood_tags.get("last") if user.mood_tags else None
    if user.platform_prefs:
        # Access the first platform in the preferences and convert it to lowercase
        platform = next(iter(user.platform_prefs.values())).lower()  # Assuming one platform preference
    else:
        platform = None
    reject_tags = set((user.reject_tags or {}).keys()) if isinstance(user.reject_tags, dict) else set(user.reject_tags or [])

    # Step 1: Start with all games
    games = db.query(Game).all()

    # Step 2: Filter out rejected genres or vibes
    def is_rejected(game):
        game_genres = set(game.genre or [])
        game_vibes = set(game.game_vibes or [])
        return bool(game_genres & reject_tags or game_vibes & reject_tags)

    filtered_games = [g for g in games if not is_rejected(g)]

    # Step 3: Score games based on user profile
    def score_game(game):
        score = 0

        # 🎯 Match mood
        if mood and game.mood_tags and mood in game.mood_tags:
            score += 2

        # 🕹 Match platform
        if platform:
            platform_match = any(p.platform.lower() == platform for p in game.platforms)
            if platform_match:
                score += 1

        return score

    # Step 4: Sort by score descending
    ranked = sorted(filtered_games, key=score_game, reverse=True)

    return ranked[:top_k]
