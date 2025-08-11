from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from app.db.models.game_platforms import GamePlatform
from app.db.models.game_recommendations import GameRecommendation
from app.services.user_profile_update import set_pending_action
from app.db.models.enums import PhaseEnum
from app.db.models.game import Game
from sqlalchemy import func, cast, Integer
from scipy.spatial.distance import cosine
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified
model = SentenceTransformer("BAAI/bge-base-en-v1.5")

# Function to get the platform link for a given game and preferred platform
def get_game_platform_link(game_id, preferred_platform, db_session):
    if preferred_platform is not None:
        platform_entry = db_session.query(GamePlatform).filter_by(
            game_id=game_id,
            platform=preferred_platform
        ).first()
        if platform_entry and platform_entry.link:
            return platform_entry.link
    else:
        platform_entry = db_session.query(GamePlatform).filter(
            GamePlatform.game_id == game_id,
            GamePlatform.link != None,
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
    session.meta_data = session.meta_data or {}
    session.meta_data["session_phase"] = "Activate"
    # Step 1: Determine platform preference from session or user
    platform = None
    if session.platform_preference:
        platform = session.platform_preference[-1]
        print(f"[Step 1] Platform from session: {platform}")
    else:
        print("[Step 1] No platform preference found.")

    last_session_game = False
    # Step 2: Determine genre preference from session or user (use last genre from session)
    last_session_liked_game = db.query(GameRecommendation).filter(
        GameRecommendation.user_id == user.user_id,
        GameRecommendation.accepted == True,
        GameRecommendation.session_id != session.session_id
    ).order_by(GameRecommendation.timestamp.desc()).first()
    
    # Check if the last liked game exists before trying to access its genre
    genre = session.genre if session.genre else None
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

    reject_genres = set((session.meta_data or {}).get("reject_tags", {}).get("genre", []))
    rejected_genres_lower = [genre.strip().lower() for genre in reject_genres]

    filtered_query = base_query.filter(
        text("""
            NOT EXISTS (
                SELECT 1
                FROM unnest(games.genre) AS g
                WHERE LOWER(g) = ANY(:rejected_genres)
            )
        """)
    ).params(rejected_genres=rejected_genres_lower)
    base_query = filtered_query
    print(f"[Step 3.1] Number of games after reject_genres filter: {base_query.count()}")
    reject_genre_games = filtered_query.all()
    print(f"[Step 3.2] after reject_genres filter: {len(reject_genre_games)}")

    session_gameplay_embedding = None
    session_preference_embedding = None
    session_disliked_embedding = None
    tone = session.meta_data.get("tone", {})
    mood = session.meta_data.get("mood", {})

    if session.gameplay_elements:
        session_gameplay_embedding = model.encode(' '.join(session.gameplay_elements))
        print(f"[Step 9] Embedded gameplay_elements: {session.gameplay_elements}")
    if session.preferred_keywords or (tone or mood):
        session_preference_embedding = model.encode(' '.join(session.preferred_keywords + [tone] + [mood]))
        print(f"[Step 9] Embedded preferred_keywords: {session.preferred_keywords, tone, mood}")
    if session.disliked_keywords:
        session_disliked_embedding = model.encode(' '.join(session.disliked_keywords))
        print(f"[Step 9] Embedded disliked_keywords: {session.disliked_keywords}")

    # Step 4: Early fallback if no platform or session information is available
    if platform is None and genre is None and not session.gameplay_elements and not session.preferred_keywords and not session.disliked_keywords:
        if last_session_liked_game:
            print("[Step 4] Early fallback: Using last liked game from session.")
            
            platform = last_session_liked_game.platform
            genre = last_session_liked_game.genre if last_session_liked_game.genre else last_session_liked_game.game.genre
            gameplay_elements = last_session_liked_game.keywords.get("gameplay_elements", []) if last_session_liked_game.keywords else None
            preferred_keywords = last_session_liked_game.keywords.get("preferred_keywords", []) if last_session_liked_game.keywords else None
            disliked_keywords = last_session_liked_game.keywords.get("disliked_keywords", []) if last_session_liked_game.keywords else None

            if gameplay_elements is not None:
                session_gameplay_embedding = model.encode(' '.join(gameplay_elements))
                print(f"[Step 9] Embedded gameplay_elements: {gameplay_elements}")
            if preferred_keywords is not None:
                session_preference_embedding = model.encode(' '.join(preferred_keywords))
                print(f"[Step 9] Embedded preferred_keywords: {preferred_keywords}")
            if preferred_keywords is not None:
                session_disliked_embedding = model.encode(' '.join(preferred_keywords))
                print(f"[Step 9] Embedded disliked_keywords: {disliked_keywords}")
            last_session_game = True
        
        else:
            print("[Step 4] Early fallback: No platform or preferences info, recommending random game.")
            random_game = base_query.order_by(func.random()).first()
            if not random_game:
                print("[Step 4] Early fallback: No games in database.")
                return None, None
            platforms = db.query(GamePlatform.platform).filter(
                GamePlatform.game_id == random_game.game_id
            ).all()
            link = get_game_platform_link(random_game.game_id, platform, db)
            # Save recommendation
            session.game_rejection_count += 1
            flag_modified(session, "game_rejection_count")
            game_rec = GameRecommendation(
                session_id=session.session_id,
                user_id=user.user_id,
                game_id=random_game.game_id,
                platform=session.platform_preference[-1] if session.platform_preference else None,
                genre=session.genre if session.genre else None,
                tone=session.meta_data.get("tone", {}) if session.meta_data.get("tone") else None,
                keywords={
                    "gameplay_elements": session.gameplay_elements or [],
                    "preferred_keywords": session.preferred_keywords or [],
                    "disliked_keywords": session.disliked_keywords or []
                },
                mood_tag=session.exit_mood if session.exit_mood else None,
                accepted=None
            )
            db.add(game_rec)
            session.last_recommended_game = random_game.title
            session.phase = PhaseEnum.FOLLOWUP
            session.meta_data["ask_confirmation"] = True
            db.commit()
            # session.followup_triggered = True
            print(f"[Step 4] Early fallback: Random game recommended: {random_game.title}")
            await set_pending_action(db, session,'send_link',link)
            return {
                "title": random_game.title,
                "description": random_game.description if random_game.description else None,
                "genre": random_game.genre,
                "game_vibes": random_game.game_vibes,
                "complexity": random_game.complexity,
                "visual_style": random_game.graphical_visual_style,
                "has_story": random_game.has_story,
                "platforms": [p[0] for p in platforms],
                "link": link,
                "last_session_game": {
                    "is_last_session_game": last_session_game,
                    "title": last_session_liked_game.game.title if last_session_liked_game else None,
                    "game_id": last_session_liked_game.game.game_id if last_session_liked_game else None
                }
            }, False
        
    if last_session_game and last_session_liked_game:
        base_query = base_query.filter(Game.game_id != last_session_liked_game.game_id)
        print(f"[Step 3.3] Excluded last session liked game: {last_session_liked_game.game_id}")

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
    # if genre:
    #     print(f"[Step 6] Applying filter for genres: {', '.join(genre)}")

    #     # Use robust, case-insensitive genre filter for all genres in session
    #     genre_filters = [
    #         text("EXISTS (SELECT 1 FROM unnest(genre) AS g WHERE LOWER(g) = :g)")
    #         for g in genre
    #     ]
    #     filtered_query = base_query.filter(
    #         or_(*[f.params(g=g.strip().lower()) for g, f in zip(genre, genre_filters)])
    #     )

    #     test_games = filtered_query.all()
    #     print(f"[Step 6] Number of games after genre filter: {len(test_games)}")

    #     if not test_games:
    #         print(f"[:information_source:] No games found with all genres '{', '.join(genre)}'.")
    #         # Fallback to the last genre if no games are found
    #         print(f"[:information_source:] Falling back to last genre: {genre[-1]}")
    #         last_genre = genre[-1]
    #         filtered_query = base_query.filter(
    #             text("EXISTS (SELECT 1 FROM unnest(genre) AS g WHERE LOWER(g) = :g)")
    #         ).params(g=last_genre.strip().lower())

    #         test_games = filtered_query.all()
    #         if not test_games:
    #             print("[Step 6] No games found with last genre. Returning None.")
    #             return None, False
    #         else:
    #             base_query = filtered_query
    #             print(f"[Step 6] Genre filter applied, {len(test_games)} games match.")
    #     else:
    #         base_query = filtered_query
    #         print(f"[Step 6] Genre filter applied, {len(test_games)} games match.")

    if genre:
        last_genre = genre[-1]  # Get the last genre from the genre list in session
        print(f"[Step 6] Applying filter for the last genre: {last_genre}")
        # Use robust, case-insensitive genre filter
        filtered_query = base_query.filter(
            text("EXISTS (SELECT 1 FROM unnest(genre) AS g WHERE LOWER(g) = :g)")
        ).params(g=last_genre.strip().lower())
        test_games = filtered_query.all()
        print(f"[Step 6] Number of games after genre filter: {len(test_games)}")
        if not test_games:
            print(f"[:information_source:] No games found with genre '{last_genre}'.")
            return None, False
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

    base_games = base_query.all()
    print(f"[Step 7] Number of candidate games after filters: {len(base_games)}")

    # Step 8: If no games after applying all filters, fallback to random game
    if not base_games:
        return None, False

    # Thresholds and weights
    DISLIKE_THRESHOLD = 0.5  # similarity above which game is rejected
    PENALTY_WEIGHT = 0.5     # penalty weight for dislike similarity
    GAMEPLAY_WEIGHT = 0.6
    PREFERENCE_WEIGHT = 0.4

    HIGH_PENALTY_MOODS = {"sad", "angry", "anxious", "bored", "restless", "frustrated", "tired", "melancholic", "insecure","overwhelmed", "pessimistic", "stressed", "ashamed", "guilty", "shy", "fearful", "apathetic","sarcastic", "moody", "lonely"}
    mood = session.exit_mood if session.exit_mood else None
    if mood in HIGH_PENALTY_MOODS:
        PENALTY_WEIGHT = 0.8  # Higher penalty for disliked similarity in high-penalty moods
    
    print(f"PENALTY_WEIGHT : {PENALTY_WEIGHT}---------------------")

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
        genre=session.genre if session.genre else None,
        tone=session.meta_data.get("tone", {}) if session.meta_data.get("tone") else None,
        mood_tag=session.exit_mood if session.exit_mood else None,
        keywords={
            "gameplay_elements": session.gameplay_elements or [],
            "preferred_keywords": session.preferred_keywords or [],
            "disliked_keywords": session.disliked_keywords or []
        },
        accepted=None
    )
    session.game_rejection_count += 1
    flag_modified(session, "game_rejection_count")
    db.add(game_rec)
    session.meta_data["ask_confirmation"] = True
    session.last_recommended_game = top_game.title
    db.commit()
    session.phase = PhaseEnum.FOLLOWUP
    # session.followup_triggered = True
    print(f"[Step 14] Recommendation saved for game: {top_game.title}")

    # Step 15: Return recommendation info and age prompt flag
    print("availables game not random ................")
    print(f"[Step 15] Last session game is used: {last_session_liked_game.game.title if last_session_liked_game else None}")
    await set_pending_action(db, session,'send_link',link)
    return {
            "title": top_game.title,
            "description": top_game.description if top_game.description else None,
            "genre": top_game.genre,
            "game_vibes": top_game.game_vibes,
            "complexity": top_game.complexity,
            "visual_style": top_game.graphical_visual_style,
            "has_story": top_game.has_story,
            "platforms": [p[0] for p in platforms],
            "link": link,
            "last_session_game": {
                "is_last_session_game": last_session_game,
                "title": last_session_liked_game.game.title if last_session_liked_game is not None else None,
                "game_id": last_session_liked_game.game.game_id if last_session_liked_game is not None else None
                }
        }, age_ask_required
    