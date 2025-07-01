from rapidfuzz import process
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models.session import Session
from sqlalchemy.dialects.postgresql import UUID
from app.db.models.game_recommendations import GameRecommendation
from app.db.models.user_profile import UserProfile
from app.db.models import Game
from typing import Dict
from datetime import date
from app.services.mood_engine import detect_mood_from_text
from app.services.session_manager import update_or_create_session_mood
from app.utils.genre import get_best_genre_match 
from app.utils.platform_utils import get_best_platform_match


# ✅ Update user profile with parsed classification fields
def update_game_feedback_from_json(db, user_id: UUID, feedback_data: list) -> None:
    if not isinstance(feedback_data, list) or not feedback_data:
        print("🟡 No valid game feedback provided. Skipping update.")
        return

    # Load all game titles and IDs
    all_games = db.query(Game.game_id, Game.title).all()
    title_lookup = {g.title: g.game_id for g in all_games}

    user = db.query(UserProfile).filter_by(user_id=user_id).first()
    if not user:
        print("❌ User not found.")
        return

    user.likes = user.likes or {}
    user.dislikes = user.dislikes or {}
    user.likes.setdefault("like", [])
    user.dislikes.setdefault("dislike", [])

    for feedback in feedback_data:
        game_title = feedback.get("game", "")
        accepted = feedback.get("accepted", None)
        reason = feedback.get("reason", "").strip()

        # ✅ NEW: Skip if game title is missing or invalid
        if not game_title or game_title.strip().lower() in ["none", "null", ""]:
            print("⛔ Skipping feedback: game title is missing or invalid.")
            continue

        # ✅ CHANGED: Use rapidfuzz instead of fuzzywuzzy
        match = process.extractOne(game_title, title_lookup.keys(), score_cutoff=75)
        if not match:
            print(f"❌ No match found for game title: {game_title}")
            continue

        matched_title = match[0]  # rapidfuzz returns (match, score, index)
        matched_game_id = title_lookup[matched_title]
        print(f"🎯 Matched '{game_title}' → '{matched_title}' (ID: {matched_game_id})")

        # Try to find existing recommendation
        game_rec = db.query(GameRecommendation).filter_by(user_id=user_id, game_id=matched_game_id).first()

        if not game_rec:
            print(f"⚠️ No GameRecommendation found for game '{matched_title}' and user. Creating new entry.")
            game_rec = GameRecommendation(
                session_id=None,
                user_id=user_id,
                game_id=matched_game_id,
                accepted=accepted,
                reason=reason
            )
            db.add(game_rec)
        else:
            game_rec.accepted = accepted
            game_rec.reason = reason
            print(f"✅ Updated: accepted={accepted}, reason='{reason}'")

        # ✅ Only update likes/dislikes if valid title matched
        if accepted is True and str(matched_game_id) not in user.likes["like"]:
            user.likes["like"].append(str(matched_game_id))
            print(f"👍 Added to likes: {matched_game_id}")
        elif accepted is False and str(matched_game_id) not in user.dislikes["dislike"]:
            user.dislikes["dislike"].append(str(matched_game_id))
            print(f"👎 Added to dislikes: {matched_game_id}")

    db.commit()
    print("💾 All feedback processed and saved.")




# ✅ Update user profile with parsed classification fields
def update_user_from_classification(db: Session, user, classification: dict,session):

    print(f"update classification : {classification}")
    today = date.today().isoformat()

    name = classification.get("name")
    mood = classification.get("mood")
    game_vibe = classification.get("game_vibe")
    genre = classification.get("genre")
    print(f"update genre :; {genre}")
    platform = classification.get("platform_pref")
    region = classification.get("region")
    age = classification.get("age")
    story_pref = classification.get("story_pref")
    playtime = classification.get("playtime_pref")
    reject_tags = classification.get("regect_tag", [])
    game_feedback = classification.get("game_feedback", [])

    # -- Name
    if name and name != "None":
        user.name = name.strip().title()
        user.last_updated["name"] = str(datetime.utcnow())

    # -- Mood
    if mood and mood != "None":
        mood_result = detect_mood_from_text(db, mood)
        user.mood_tags[today] = mood_result
        user.last_updated["mood_tags"] = str(datetime.utcnow())
        # update_or_create_session_mood(db, user, new_mood=mood_result)

    # -- Game Vibe
    if game_vibe and game_vibe != "None":
        user.game_vibe = game_vibe.lower()
        user.last_updated["game_vibe"] = str(datetime.utcnow())

    # -- Genre Preferences
    if genre and genre != "None":
        matched_genre = get_best_genre_match(db=db, input_genre=genre)
        print(f"update matched genre : {matched_genre}")
        if matched_genre:
            user.genre_prefs.setdefault(today, [])
            if matched_genre not in user.genre_prefs[today]:
                user.genre_prefs[today].append(matched_genre)
            user.last_updated["genre_prefs"] = str(datetime.utcnow())

    # -- Platform Preferences
    if platform and platform != "None":
        matched_platform = get_best_platform_match(db=db, user_input=platform)
        if matched_platform:
            user.platform_prefs.setdefault(today, [])
            if matched_platform not in user.platform_prefs[today]:
                user.platform_prefs[today].append(matched_platform)
            user.last_updated["platform_prefs"] = str(datetime.utcnow())

    # -- Region
    if region and region != "None":
        user.region = region.strip().title()
        user.last_updated["region"] = str(datetime.utcnow())

    # -- Age Range
    if age and age != "None":
        user.age_range = age.strip()
        user.last_updated["age_range"] = str(datetime.utcnow())

    # -- Story Preference
    if story_pref is not None and story_pref != "None":
        user.story_pref = bool(story_pref)
        user.last_updated["story_pref"] = str(datetime.utcnow())

    # -- Playtime
    if playtime and playtime != "None":
        user.playtime = playtime.strip().lower()
        user.last_updated["playtime"] = str(datetime.utcnow())

    # -- Reject Tags (Genre vs Platform)
    if isinstance(reject_tags, list):
        print(f"[🛑 Raw reject_tags]: {reject_tags}")

        # Ensure proper structure
        if not isinstance(user.reject_tags, dict):
            user.reject_tags = {}

        user.reject_tags.setdefault("genre", [])
        user.reject_tags.setdefault("platform", [])
        user.reject_tags.setdefault("other", [])
        for tag in reject_tags:
            tag_clean = tag.strip().lower()

            # Try platform match
            matched_platform = get_best_platform_match(user_input=tag_clean, db=db)
            if matched_platform:
                if matched_platform not in user.reject_tags["platform"]:
                    user.reject_tags["platform"].append(matched_platform)
                print(f"✅ Platform matched: {tag_clean} → {matched_platform}")
                continue

            # Try genre match
            matched_genre = get_best_genre_match(input_genre=tag_clean, db=db)
            if matched_genre:
                if matched_genre not in user.reject_tags["genre"]:
                    user.reject_tags["genre"].append(matched_genre)
                print(f"✅ Genre matched: {tag_clean} → {matched_genre}")
                continue

            # If no match, store in "other"
            if tag_clean not in user.reject_tags["other"]:
                user.reject_tags["other"].append(tag_clean)
                print(f"⚠️ No match found for: {tag_clean} → added to 'other'")

        user.last_updated["reject_tags"] = str(datetime.utcnow())

    update_game_feedback_from_json(db=db, user_id=user.user_id, feedback_data=game_feedback)

    user.last_updated["game_feedback"] = str(datetime.utcnow())

    db.commit()