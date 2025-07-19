from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from app.db.models.mood_cluster import MoodCluster
from app.db.models.game_platforms import GamePlatform
from app.db.models.game_recommendations import GameRecommendation
from app.db.models.enums import PhaseEnum, SenderEnum
from app.db.models.session import Session as UserSession
from app.db.models.game import Game
from sqlalchemy import func, cast, Integer, or_, and_
from scipy.spatial.distance import cosine
from datetime import datetime
import numpy as np
from sqlalchemy import text
model = SentenceTransformer("BAAI/bge-base-en-v1.5")

# Function to get the platform link for a given game and preferred platform
def get_game_platform_link(game_id, preferred_platform, db_session):
    platform_entry = db_session.query(GamePlatform).filter_by(
        game_id=game_id,
        platform=preferred_platform
    ).first()
    if platform_entry and platform_entry.link:
        return platform_entry.link
    return None

# Helper function to convert vector arrays to a consistent format
def to_vector(v):
    if v is None:
        return None
    v = np.array(v)
    if v.ndim == 2:
        return v.flatten()
    if v.ndim == 1:
        return v
    return None

# Main game recommendation function
async def game_recommendation(db: Session, user, session):
    today = datetime.utcnow().date().isoformat()

    # Step 1: Determine platform preference from session or user
    platform = None
    if session.platform_preference:
        platform = session.platform_preference[-1]
        print(f"[Step 1] Platform from session: {platform}")
    elif user.platform_prefs and today in user.platform_prefs and user.platform_prefs[today]:
        platform = user.platform_prefs[today][-1]
        print(f"[Step 1] Platform from user today prefs: {platform}")
    elif user.platform_prefs:
        for day_prefs in reversed(user.platform_prefs.values()):
            if day_prefs:
                platform = day_prefs[-1]
                print(f"[Step 1] Platform from user recent prefs: {platform}")
                break
    else:
        print("[Step 1] No platform preference found.")

    # Step 2: Determine genre preference from session or user (use last genre from session)
    genre = session.genre if session.genre else (
        user.genre_prefs.get(today, []) if user.genre_prefs and today in user.genre_prefs
        else next((g for g in reversed(user.genre_prefs.values()) if g), []) if user.genre_prefs else []
    )
    print(f"[Step 2] Genre: {genre}")

    # Step 3: Exclude rejected and already recommended games
    rejected_game_ids = set(session.rejected_games or [])
    recommended_ids = set(
        r[0] for r in db.query(GameRecommendation.game_id).filter(
            GameRecommendation.session_id == session.session_id
        )
    )
    print(f"[Step 3] Rejected games count: {len(rejected_game_ids)}, Recommended games count: {len(recommended_ids)}")

    base_query = db.query(Game).filter(
        ~Game.game_id.in_(rejected_game_ids),
        ~Game.game_id.in_(recommended_ids)
    )
    print(f"[Step 3] Number of games before platform filter: {base_query.count()}")

    # Step 4: Early fallback if no platform or session information is available
    if platform is None and genre is None and not session.gameplay_elements and not session.preferred_keywords and not session.disliked_keywords:
        print("[Step 4] Early fallback: No platform or preferences info, recommending random game.")
        random_game = db.query(Game).order_by(func.random()).first()
        if not random_game:
            print("[Step 4] Early fallback: No games in database.")
            return None, None
        platforms = db.query(GamePlatform.platform).filter(
            GamePlatform.game_id == random_game.game_id
        ).all()
        link = get_game_platform_link(random_game.game_id, platform, db)
        # Save recommendation
        game_rec = GameRecommendation(
            session_id=session.session_id,
            user_id=user.user_id,
            game_id=random_game.game_id,
            platform=None,
            mood_tag=None,
            accepted=None
        )
        db.add(game_rec)
        db.commit()
        session.phase = PhaseEnum.FOLLOWUP
        session.followup_triggered = True
        print(f"[Step 4] Early fallback: Random game recommended: {random_game.title}")
        return {
            "title": random_game.title,
            "description": random_game.description[:200] if random_game.description else None,
            "genre": random_game.genre,
            "game_vibes": random_game.game_vibes,
            "mechanics": random_game.mechanic,
            "visual_style": random_game.graphical_visual_style,
            "has_story": random_game.has_story,
            "platforms": [p[0] for p in platforms],
            "link": link
        }, False

    # Step 5: Filter by platform availability
    if platform:
        platform_game_ids = db.query(GamePlatform.game_id).filter(
            func.lower(GamePlatform.platform) == platform.lower()
        ).all()
        platform_game_ids = [g[0] for g in platform_game_ids]
        base_query = base_query.filter(Game.game_id.in_(platform_game_ids))
        print(f"[Step 5] Filtered games by platform '{platform}', candidates left: {len(platform_game_ids)}")
    else:
        print("[Step 5] No platform filter applied.")

    # Step 6: Apply genre filter after platform filtering
    # Step 6: Apply genre filter after platform filtering
    if genre:
        last_genre = genre[-1]  # Get the last genre from the genre list in session
        print(f"[Step 6] Applying filter for the last genre: {last_genre}")

        # Use robust, case-insensitive genre filter
        filtered_query = base_query.filter(
            text("EXISTS (SELECT 1 FROM unnest(genre) AS g WHERE LOWER(g) = :g)")
        ).params(g=last_genre.strip().lower())
        print("-----------------------", filtered_query)

        test_games = filtered_query.all()
        print(f"[Step 6] Number of games after genre filter: {len(test_games)}")

        if not test_games:
            print(f"[:information_source:] No games found with genre '{last_genre}'.")
            # handle fallback here if needed
        else:
            base_query = filtered_query
            print(f"[Step 6] Genre filter applied, {len(test_games)} games match.")



    # Step 7: Filter by user age if available
    user_age = None
    if user.age_range:
        try:
            user_age = int(user.age_range)
            base_query = base_query.filter(
                cast(Game.age_rating, Integer) <= user_age
            )
            print(f"[Step 7] Applied age filter: user age = {user_age}")
        except ValueError:
            print("[Step 7] Invalid user age; skipping age filter.")
    else:
        print("[Step 7] No user age available; skipping age filter.")

    session.game_rejection_count += 1
    base_games = base_query.all()
    print(f"[Step 7] Number of candidate games after filters: {len(base_games)}")

    # Step 8: If no games after applying all filters, fallback to random game
    if not base_games:
        return None, False

    # Step 9: Embed session gameplay_elements, preferred_keywords, disliked_keywords at runtime
    session_gameplay_embedding = None
    session_preference_embedding = None
    session_disliked_embedding = None

    if session.gameplay_elements:
        session_gameplay_embedding = model.encode(' '.join(session.gameplay_elements))
        print(f"[Step 9] Embedded gameplay_elements: {session.gameplay_elements}")
    if session.preferred_keywords:
        session_preference_embedding = model.encode(' '.join(session.preferred_keywords))
        print(f"[Step 9] Embedded preferred_keywords: {session.preferred_keywords}")
    if session.disliked_keywords:
        session_disliked_embedding = model.encode(' '.join(session.disliked_keywords))
        print(f"[Step 9] Embedded disliked_keywords: {session.disliked_keywords}")

    # Thresholds and weights
    DISLIKE_THRESHOLD = 0.5  # similarity above which game is rejected
    PENALTY_WEIGHT = 0.5     # penalty weight for dislike similarity
    GAMEPLAY_WEIGHT = 0.6
    PREFERENCE_WEIGHT = 0.4

    def compute_score(game: Game):
        gameplay_sim = 0
        preference_sim = 0
        dislike_sim = 0

        game_gameplay_embedding = to_vector(game.gameplay_embedding)
        game_preference_embedding = to_vector(game.preference_embedding)

        if session_gameplay_embedding is not None and game_gameplay_embedding is not None:
            gameplay_sim = 1 - cosine(session_gameplay_embedding, game_gameplay_embedding)

        if session_preference_embedding is not None and game_preference_embedding is not None:
            preference_sim = 1 - cosine(session_preference_embedding, game_preference_embedding)

        if session_disliked_embedding is not None and game_preference_embedding is not None:
            dislike_sim = 1 - cosine(session_disliked_embedding, game_preference_embedding)
            if dislike_sim >= DISLIKE_THRESHOLD:
                print(f"[Step 10] Game '{game.title}' excluded due to disliked similarity: {dislike_sim}")
                return 0

        score = GAMEPLAY_WEIGHT * gameplay_sim + PREFERENCE_WEIGHT * preference_sim
        # Soft penalty for disliked similarity if below threshold
        if session_disliked_embedding is not None and dislike_sim < DISLIKE_THRESHOLD:
            score -= PENALTY_WEIGHT * dislike_sim
        return max(score, 0.01)

    # Step 11: Score and rank candidate games
    scored_games = [(g, compute_score(g)) for g in base_games]
    ranked_games = sorted(scored_games, key=lambda x: x[1], reverse=True)

    if not ranked_games:
        print("[Step 11] No games scored above zero after embedding similarity.")
        return None, None

    # Optionally exclude last recommended game title
    if session.last_recommended_game:
        ranked_games = [rg for rg in ranked_games if rg[0].title != session.last_recommended_game]
        print(f"[Step 11] Excluded last recommended game: {session.last_recommended_game}")
        if not ranked_games:
            print("[Step 11] No candidates after excluding last recommended game.")
            return None, None

    top_game = ranked_games[0][0]
    top_game_score = ranked_games[0][1]
    print(f"[Step 11] Top game candidate: {top_game.title} with score {top_game_score:.4f}")

    # Step 12: Age verification check for recommendation
    age_ask_required = False
    try:
        game_age = int(top_game.age_rating) if top_game.age_rating else None
    except ValueError:
        game_age = None

    if user_age is None and game_age is not None and game_age >= 18:
        age_ask_required = True
        print("[Step 12] Age verification required: user age unknown, game is 18+")
    if user_age is not None and game_age is not None and game_age > user_age:
        age_ask_required = True
        print(f"[Step 12] Age verification required: user age {user_age}, game age rating {game_age}")

    # Step 13: Retrieve platforms & purchase link
    platforms = db.query(GamePlatform.platform).filter(
        GamePlatform.game_id == top_game.game_id
    ).all()
    link = get_game_platform_link(top_game.game_id, platform, db)
    print(f"[Step 13] Found platforms: {[p[0] for p in platforms]}, link: {link}")

    # Step 14: Save the recommendation record
    game_rec = GameRecommendation(
        session_id=session.session_id,
        user_id=user.user_id,
        game_id=top_game.game_id,
        platform=platform,
        mood_tag=None,  # mood tagging not used here, add if needed
        accepted=None
    )
    db.add(game_rec)
    db.commit()
    session.phase = PhaseEnum.FOLLOWUP
    session.followup_triggered = True
    print(f"[Step 14] Recommendation saved for game: {top_game.title}")

    # Step 15: Return recommendation info and age prompt flag
    return {
        "title": top_game.title,
        "description": top_game.description if top_game.description else None,
        "genre": top_game.genre,
        "game_vibes": top_game.game_vibes,
        "mechanics": top_game.mechanic,
        "visual_style": top_game.graphical_visual_style,
        "has_story": top_game.has_story,
        "platforms": [p[0] for p in platforms],
        "link": link
    }, age_ask_required