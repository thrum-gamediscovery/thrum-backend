from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from app.db.models.mood_cluster import MoodCluster
from app.db.models.game_platforms import GamePlatform
from app.db.models.game_recommendations import GameRecommendation
from app.db.models.enums import PhaseEnum, SenderEnum
from app.db.models.session import Session as UserSession
from app.db.models.game import Game
from sqlalchemy import func, cast, Integer, or_
from scipy.spatial.distance import cosine
from datetime import datetime
from typing import Optional, Dict, Tuple, List
import numpy as np
import random

model = SentenceTransformer("all-MiniLM-L12-v2")

async def game_recommendation(db: Session, user, session):
    today = datetime.utcnow().date().isoformat()

    # Step 1: Pull platform, genre, mood
    platform = session.platform_preference[-1] if session.platform_preference else (
        user.platform_prefs.get(today, [])[-1] if user.platform_prefs and today in user.platform_prefs and user.platform_prefs[today]
        else next((p[-1] for p in reversed(user.platform_prefs.values()) if p), None) if user.platform_prefs else None
    )
    genre = session.genre[-1] if session.genre else (
        user.genre_prefs.get(today, [])[-1] if user.genre_prefs and today in user.genre_prefs and user.genre_prefs[today]
        else next((g[-1] for g in reversed(user.genre_prefs.values()) if g), None) if user.genre_prefs else None
    )
    mood = session.exit_mood if session.exit_mood else (
        user.mood_tags.get(today) if user.mood_tags and today in user.mood_tags
        else next(reversed(user.mood_tags.values()), None) if user.mood_tags else None
    )
    print(f"[🎯] Final values — platform: {platform}, genre: {genre}, mood: {mood}")

    # Step 2: Base query and rejection filters
    rejected_game_ids = set(session.rejected_games or [])
    recommended_ids = set(
        r[0] for r in db.query(GameRecommendation.game_id).filter(
            GameRecommendation.session_id == session.session_id
        )
    )
    reject_genres = set((session.meta_data or {}).get("reject_tags", {}).get("genre", []))

    base_query = db.query(Game).filter(
        Game.mood_embedding.isnot(None),
        Game.game_embedding.isnot(None),
        ~Game.game_id.in_(rejected_game_ids),
        ~Game.game_id.in_(recommended_ids)
    )

    if reject_genres:
        genre_filters = [
            Game.genre.any(func.lower(genre.strip().lower()))
            for genre in reject_genres
        ]
        base_query = base_query.filter(~or_(*genre_filters))
    
    print("💡 Input check:.......................................................", genre, platform)

    if genre:
        base_query = base_query.filter(
            Game.genre.any(func.lower(genre.strip().lower()))
        )
    
    if platform:
        platform_game_ids = db.query(GamePlatform.game_id).filter(
            func.lower(GamePlatform.platform) == platform.lower()
        ).all()
        platform_game_ids = [g[0] for g in platform_game_ids]
        base_query = base_query.filter(Game.game_id.in_(platform_game_ids))

    # Step 3: Filter games above user age if user_age is known
    user_age = None
    if user.age_range:
        try:
            user_age = int(user.age_range)
        except ValueError:
            pass

    if user_age is not None:
        base_query = base_query.filter(
            cast(Game.age_rating, Integer) <= user_age
        )
    session.game_rejection_count += 1
    base_games = base_query.all()
    if not base_games:
        return None, None
        # Step 1.5: Cold start → recommend random safe game
    if not platform and not genre and not mood:
        print("[🧊] Cold start: returning a safe random game.")
        random_game = base_query.order_by(func.random()).first()

        if not random_game:
            return None, None

        platforms = db.query(GamePlatform.platform).filter(
            GamePlatform.game_id == random_game.game_id
        ).all()

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

        return {
            "title": random_game.title,
            "description": random_game.description[:200] if random_game.description else None,
            "genre": random_game.genre,
            "game_vibes": random_game.game_vibes,
            "mechanics": random_game.mechanics,
            "visual_style": random_game.visual_style,
            "has_story": random_game.has_story,
            "platforms": [p[0] for p in platforms]
        }, 0.5
    
    # Step 4: Mood cluster for soft filtering
    cluster_tags = []
    if mood:
        mood_entry = db.query(MoodCluster).filter(MoodCluster.mood == mood).first()
        if mood_entry and mood_entry.game_tags:
            cluster_tags = mood_entry.game_tags

    # Step 5: Progressive soft filters
    filter_levels = [
        {"genre": True, "platform": True, "cluster": True, "story": True},
        {"genre": True, "platform": True, "cluster": False, "story": True},
        {"genre": True, "platform": True, "cluster": True, "story": False},
        {"genre": True, "platform": False, "cluster": True, "story": True},
        {"genre": True, "platform": False, "cluster": False, "story": True},
        {"genre": True, "platform": True, "cluster": False, "story": False},
        {"genre": True, "platform": False, "cluster": False, "story": False},
    ]

    candidate_games = []
    for level in filter_levels:
        current = []
        for game in base_games:
            if level["genre"] and genre and genre.lower() not in [g.lower() for g in (game.genre or [])]:
                continue
            if level["platform"] and platform:
                platform_rows = [p[0] for p in db.query(GamePlatform.platform).filter(GamePlatform.game_id == game.game_id)]
                if platform.lower() not in [p.lower() for p in platform_rows]:
                    continue
            if level["cluster"] and cluster_tags:
                cluster_val = game.mood_tags.get("cluster") if game.mood_tags else None
                if not cluster_val or cluster_val not in cluster_tags:
                    continue
            if level.get("story", False) and user.story_pref is not None:
                if game.has_story != user.story_pref:
                    continue
            current.append(game)

        print(f"[🧪] Filter level: {level} → candidates: {len(current)}")
        if current:
            candidate_games = current
            break

    if not candidate_games:
        print("[⚠️] No match after soft filtering. Falling back to unfiltered base games.")
        candidate_games = base_games

    # Step 6: Embedding-based scoring
    user_interactions = [i for i in session.interactions if i.sender == SenderEnum.User]
    user_input = user_interactions[-1].content if user_interactions else ""
    mood_input = f"{genre} | {user_input}" if genre else None
    mood_vector = model.encode(mood_input) if mood_input else None
    genre_input = f"{genre} | {user_input}" if genre else None
    genre_vector = model.encode(genre_input) if genre_input else None

    def to_vector(v):
        if v is None:
            return None
        v = np.array(v)
        return v.flatten() if v.ndim == 2 else v if v.ndim == 1 else None

    def compute_score(game: Game):
        mood_sim = genre_sim = 0
        mood_weight = 0.6 if mood_vector is not None else 0
        genre_weight = 0.4 if genre_vector is not None else 0
        game_mood_vector = to_vector(game.mood_embedding)
        game_genre_vector = to_vector(game.game_embedding)

        if mood_vector is not None and game_mood_vector is not None:
            mood_sim = 1 - cosine(mood_vector, game_mood_vector)
        if genre_vector is not None and game_genre_vector is not None:
            genre_sim = 1 - cosine(genre_vector, game_genre_vector)

        return (mood_weight * mood_sim + genre_weight * genre_sim) if (mood_weight + genre_weight) > 0 else 0.01

    ranked = sorted([(g, compute_score(g)) for g in candidate_games], key=lambda x: x[1], reverse=True)

    # ✅ NEW: Avoid repeating the last recommended game
    if session.last_recommended_game:
        ranked = [r for r in ranked if r[0].title != session.last_recommended_game]
        if not ranked:
            return None, None

    top_game = ranked[0][0]
    age_ask_required = False

    # Step 7: Final age prompt check (only if user age is unknown and game is 18+)
    try:
        game_age = int(top_game.age_rating) if top_game.age_rating else None
    except ValueError:
        game_age = None

    if user_age is None and game_age is not None and game_age >= 18:
        age_ask_required = True

    # Step 8: Get platforms
    platforms = db.query(GamePlatform.platform).filter(
        GamePlatform.game_id == top_game.game_id
    ).all()

    # Step 9: Save recommendation
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
        "description": top_game.description[:200] if top_game.description else None,
        "genre": top_game.genre,
        "game_vibes": top_game.game_vibes,
        "mechanics": top_game.mechanics,
        "visual_style": top_game.visual_style,
        "has_story": top_game.has_story,
        "platforms": [p[0] for p in platforms],
        "age_ask_required": age_ask_required
    }, ranked[0][1]


# SECTION 3 - GAME RECOMMENDATION GENERATION & MEMORY MATCHING
def get_recommendations_by_tags(
    db: Session,
    genre_tags: List[str],
    platform_tags: List[str],
    vibe_tags: List[str],
    rejected_ids: List[str],
    max_results: int = 5
) -> List[dict]:
    print(f"🎯 Tags: genre={genre_tags}, platform={platform_tags}, vibe={vibe_tags}")
    
    games = db.query(Game).filter(Game.title != None).all()

    results = []
    for game in games:
        if str(game.game_id) in rejected_ids:
            continue

        # Check genre match
        if genre_tags and game.genre:
            if not any(g.lower() in [genre.lower() for genre in game.genre] for g in genre_tags):
                continue
        
        # Check platform match via relationship
        if platform_tags:
            game_platforms = [p.platform for p in game.platforms]
            if not any(p.lower() in [plat.lower() for plat in game_platforms] for p in platform_tags):
                continue

        emotional_blurb = generate_blurb(game, vibe_tags)
        game_platforms = [p.platform for p in game.platforms] if game.platforms else []
        
        results.append({
            "id": str(game.game_id),
            "title": game.title,
            "blurb": emotional_blurb,
            "platforms": game_platforms
        })

    if not results:
        print("⚠️ No direct match. Returning wildcard games.")
        results = get_random_games(db, rejected_ids, limit=max_results)

    return results[:max_results]

def generate_blurb(game, vibe_tags):
    if "cozy" in vibe_tags:
        return f"A slow, warm game to unwind — {game.title} feels like a rainy Sunday."
    if "solo" in vibe_tags:
        return f"Quiet but gripping — {game.title} lets you explore on your own terms."
    if "party" in vibe_tags:
        return f"Bring your crew — {game.title} turns boredom into chaos."
    
    return f"{game.title} has a unique feel — give it 10 minutes and you'll know."

def get_random_games(db, rejected_ids, limit=3):
    games = db.query(Game).filter(Game.title != None).all()
    valid = [g for g in games if str(g.game_id) not in rejected_ids]
    random.shuffle(valid)
    return [
        {
            "id": str(g.game_id),
            "title": g.title,
            "blurb": f"No idea why — but something about {g.title} might click.",
            "platforms": [p.platform for p in g.platforms] if g.platforms else []
        }
        for g in valid[:limit]
    ]

# SECTION 4 - LLM OUTPUT TUNING
def format_recommendation_output(games: List[dict], tone: str, mood: str, recall_game: str = None) -> str:
    from random import choice
    print(f"🪄 Building output with tone: {tone}, mood: {mood}")

    lines = []

    if tone == "cold":
        intro = "Here's some stuff. Maybe one fits. 🧊"
    elif tone == "vague":
        intro = "Not sure, but you might like one of these?"
    else:
        intro = choice([
            "Okay, I think I've got something 🎮",
            "Got a few picks for your vibe 🧠",
            "Alright, try these out ↓"
        ])
    lines.append(intro)

    for game in games:
        title = game["title"]
        blurb = game.get("blurb", "")
        share_hint = f"→ Send this to your crew: *{title}* might be their next obsession."

        game_line = f"\n🎲 *{title}*\n{blurb}\n{share_hint}"
        lines.append(game_line)

    if recall_game:
        lines.append(f"\n🧠 Want more like *{recall_game}*? Just say so.")

    closing = choice([
        "\n🕹 Ready when you are.",
        "\nHit me up if you want a curveball pick.",
        "\nI can keep going if you're still bored 👾"
    ])
    lines.append(closing)

    return "\n".join(lines)

# SECTION 6 - LLM EXECUTION + GAME MATCHING
def pick_best_game(user, session, db):
    from app.services.tone_classifier import classify_tone
    
    mood = session.exit_mood or session.entry_mood
    preferred_genres = list(user.genre_prefs.values())[-1] if user.genre_prefs else []
    rejected_ids = session.rejected_games or []
    tone = classify_tone(session.interactions[-1].content if session.interactions else "")

    print(f"[MATCH] Mood: {mood}, Genre: {preferred_genres}, Tone: {tone}")

    query = db.query(Game).filter(Game.title != None)

    # Filter by mood tags if available
    if mood and hasattr(Game, 'mood_tags'):
        query = query.filter(Game.mood_tags.contains({"mood": mood}))
    
    # Filter by genre
    if preferred_genres:
        genre_filters = [Game.genre.any(func.lower(g)) for g in preferred_genres]
        query = query.filter(or_(*genre_filters))

    # Exclude rejected games
    if rejected_ids:
        query = query.filter(~Game.game_id.in_(rejected_ids))

    candidates = query.all()
    print(f"[MATCH] Found {len(candidates)} candidates")

    if not candidates:
        # Fallback to any game not rejected
        candidates = db.query(Game).filter(
            Game.title != None,
            ~Game.game_id.in_(rejected_ids) if rejected_ids else True
        ).all()
        
    if not candidates:
        return None

    # Apply tone-based filtering
    if tone == "cold" and candidates:
        # Prefer shorter games for cold users
        short_games = [g for g in candidates if "short" in (g.game_vibes or [])]
        if short_games:
            candidates = short_games

    # Add some randomness
    if random.random() < 0.2 and len(candidates) > 3:
        candidates = random.sample(candidates, 3)
        print("[MATCH] Injected surprise diversity")

    pick = random.choice(candidates)
    platforms = [p.platform for p in pick.platforms] if pick.platforms else ["Unknown"]
    
    return {
        "title": pick.title,
        "platform": platforms[0] if platforms else "Unknown",
        "genre": pick.genre[0] if pick.genre else "Game",
        "summary": pick.description,
        "link": f"https://store.steampowered.com/search/?term={pick.title.replace(' ', '+')}"
    }

# SECTION 7 - OUTPUT FORMATTER + MESSAGING INTEGRATION
def format_game_reply(game: dict, mood: str = None, tone: str = "neutral", platform: str = "whatsapp") -> str:
    title = game.get("title")
    link = game.get("link")
    genre = game.get("genre")
    summary = game.get("summary")

    if tone == "cold":
        intro = random.choice([
            f"Low-key rec if you're not feelin' it: ",
            f"No pressure, but this one's a chill shot: ",
            f"Just tossing it out there: "
        ])
    elif tone == "positive":
        intro = random.choice([
            f"🔥 You might love this one: ",
            f"Let's GO. Try this: ",
            f"Based on your vibe → "
        ])
    else:
        intro = random.choice([
            f"Here's something that fits: ",
            f"Match incoming: ",
            f"Mood → Game: "
        ])

    mood_line = f"🧠 You mentioned feeling *{mood.lower()}* —" if mood else ""

    if summary:
        summary = summary.strip().split(".")[0] + "."
    else:
        summary = "Check it out."

    if platform == "whatsapp":
        return f"{intro}*{title}* on *{game['platform']}*\n{mood_line} {summary}\n{link}"
    elif platform == "discord":
        return f"**{title}** — *{genre}*\n{summary}\n🔗 {link}"
    else:
        return f"{intro}{title} ({genre})\n{summary}\nPlay it here: {link}"