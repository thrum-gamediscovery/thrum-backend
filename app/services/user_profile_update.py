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
from sqlalchemy.orm.attributes import flag_modified
from app.services.mood_engine import detect_mood_from_text
from app.services.session_manager import update_or_create_session_mood
from app.utils.genre import get_best_genre_match 
from app.utils.platform_utils import get_best_platform_match, get_default_platform
from app.services.session_memory import SessionMemory

# ✅ Update user profile with parsed classification fields
async def update_game_feedback_from_json(db, user_id: UUID, session,feedback_data: list) -> None:
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
            if str(matched_game_id) not in session.rejected_games:
                session.rejected_games.append(str(matched_game_id))
            print(f"👎 Added to dislikes: {matched_game_id}")
        user.last_updated["game_feedback"] = str(datetime.utcnow())
    db.commit()
    print("💾 All feedback processed and saved.")




# ✅ Update user profile with parsed classification fields
async def update_user_from_classification(db: Session, user, classification: dict,session):
    today = date.today().isoformat()

    if not isinstance(classification, dict):
        print(f"[BUG] update_user_from_classification: classification is not dict: {classification}")
        return
    print('classification', classification)

    name = classification.get("name")
    mood = classification.get("mood")
    genre = classification.get("genre")
    platform = classification.get("platform_pref")
    region = classification.get("region")
    age = classification.get("age")
    story_pref = classification.get("story_pref")
    playtime = classification.get("playtime_pref")
    reject_tags = classification.get("reject_tags", [])
    game_feedback = classification.get("game_feedback", [])
    find_game_title = classification.get("find_game")

    # -- Name
    if name and name != "None":
        user.name = name.strip().title()
        user.last_updated["name"] = str(datetime.utcnow())
        session.meta_data["name"] = user.name  # Store in session for short-term memory
        flag_modified(user, "name")

    # -- Mood
    if mood and mood != "None":
        mood_result = await detect_mood_from_text(db, mood)
        user.mood_tags[today] = mood_result
        if not session.entry_mood:
            session.entry_mood = mood_result
        session.exit_mood = mood_result
        session.meta_data["mood"] = mood_result
        flag_modified(user, "mood_tags")
        user.last_updated["mood_tags"] = str(datetime.utcnow())
        # update_or_create_session_mood(db, user, new_mood=mood_result)

    # -- Genre Preferences
    if genre and genre != "None":
        matched_genre = await get_best_genre_match(db=db, input_genre=genre)
        print(f"update matched genre : {matched_genre}")
        if matched_genre:
            user.genre_prefs.setdefault(today, [])
            if matched_genre in user.genre_prefs[today]:
                user.genre_prefs[today].remove(matched_genre)
            user.genre_prefs[today].append(matched_genre)
            print(f"✅ Added genre '{matched_genre}' to user.genre_prefs[{today}]")

            # ✅ Remove from user.reject_tags["genre"]
            if matched_genre in user.reject_tags.get("genre", []):
                user.reject_tags["genre"].remove(matched_genre)
                print(f"🧹 Removed genre '{matched_genre}' from user.reject_tags")

            # ✅ Remove from session.meta_data["reject_tags"]["genre"]
            if session and session.meta_data and "reject_tags" in session.meta_data:
                reject_data = session.meta_data["reject_tags"]
                if matched_genre in reject_data.get("genre", []):
                    reject_data["genre"].remove(matched_genre)
                    print(f"🧹 Removed genre '{matched_genre}' from session.meta_data['reject_tags']['genre']")

            # ✅ Add to session.genre
            if session:
                session_genres = session.genre or []
                if matched_genre in session_genres:
                    session_genres.remove(matched_genre)
                session_genres.append(matched_genre)
                session.genre = session_genres
                flag_modified(session, "genre")

                print(f"[✅ Genre added to session]: {session_genres}")
            else:
                print("❌ Session object is missing or invalid.")

            user.last_updated["genre_prefs"] = str(datetime.utcnow())

    # -- Platform Preferences
    if platform and platform != "None":
        def_promt = get_default_platform(platform)
        matched_platform = await get_best_platform_match(db=db, user_input=def_promt)
        
        if matched_platform:
            user.platform_prefs.setdefault(today, [])
            if matched_platform not in user.platform_prefs[today]:
                user.platform_prefs[today].append(matched_platform)
                print(f"✅ Added platform '{matched_platform}' to user.platform_prefs[{today}]")

            # ✅ Remove from user.reject_tags["platform"]
            if matched_platform in user.reject_tags.get("platform", []):
                user.reject_tags["platform"].remove(matched_platform)
                print(f"🧹 Removed platform '{matched_platform}' from user.reject_tags")

            # ✅ Remove from session.meta_data["reject_tags"]["platform"]
            if session and session.meta_data and "reject_tags" in session.meta_data:
                reject_data = session.meta_data["reject_tags"]
                if matched_platform in reject_data.get("platform", []):
                    reject_data["platform"].remove(matched_platform)
                    print(f"🧹 Removed platform '{matched_platform}' from session.meta_data['reject_tags']['platform']")

            # ✅ Add to session.platform_preference
            if session:
                session_platforms = session.platform_preference or []
                if matched_platform not in session_platforms:
                    session_platforms.append(matched_platform)
                    session.platform_preference = session_platforms

                    # ✅ Ensure SQLAlchemy detects the change
                    flag_modified(session, "platform_preference")

                    print(f"[✅ Platform added to session]: {session_platforms}")
                else:
                    print(f"[ℹ️ Platform already present]: {matched_platform}")
            else:
                print("❌ Session object is missing or invalid.")

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
        session.story_preference = bool(story_pref)
        flag_modified(user, "story_pref")
        flag_modified(session, "story_preference")
        user.last_updated["story_pref"] = str(datetime.utcnow())

    # -- Playtime
    if playtime and playtime != "None":
        user.playtime = playtime.strip().lower()
        flag_modified(user, "playtime")
        user.last_updated["playtime"] = str(datetime.utcnow())

    # -- find game
    if find_game_title and find_game_title.lower() != "none":
            # Load all game titles and IDs
            all_games = db.query(Game.game_id, Game.title).all()
            title_lookup = {g.title: g.game_id for g in all_games}
            match = process.extractOne(find_game_title.strip(), title_lookup.keys(), score_cutoff=75)
            if match:
                matched_title = match[0]
                matched_game_id = str(title_lookup[matched_title])  # Store as string
                session.meta_data["find_game"] = matched_game_id
                flag_modified(session, "meta_data")
                print(f"🎯 Stored matched find_game → '{matched_title}' (ID: {matched_game_id}) in session.meta_data")
            else:
                print(f"❌ No match found for 'find_game' title: {find_game_title}")

    # -- Reject Tags (Genre vs Platform)
    if isinstance(reject_tags, list):
        print(f"[🛑 Raw reject_tags]: {reject_tags}")

        # Ensure proper structure
        if not isinstance(user.reject_tags, dict):
            user.reject_tags = {}

        # Ensure the session meta_data exists
        if session.meta_data is None:
            session.meta_data = {}
        # Initialize the reject_tags structure if not already initialized
        if "reject_tags" not in session.meta_data:
            session.meta_data["reject_tags"] = {"genre": [], "platform": [], "other": []}    
        reject_data = session.meta_data["reject_tags"]
        user.reject_tags.setdefault("genre", [])
        user.reject_tags.setdefault("platform", [])
        user.reject_tags.setdefault("other", [])
        
        for tag in reject_tags:
            tag_clean = tag.strip().lower()

            # ✅ Try platform match
            def_promt = get_default_platform(tag_clean)
            matched_platform = await get_best_platform_match(db=db, user_input=def_promt)
            if matched_platform or matched_platform is not None:
                if matched_platform not in user.reject_tags["platform"]:
                    user.reject_tags["platform"].append(matched_platform)
                if matched_platform not in reject_data["platform"]:
                    reject_data["platform"].append(matched_platform)
                print(f"✅ Platform matched: {tag_clean} → {matched_platform}")

                # ✅ Remove from user.platform_prefs
                for day, platforms in user.platform_prefs.items():
                    if matched_platform in platforms:
                        platforms.remove(matched_platform)
                        print(f"🧹 Removed rejected platform '{matched_platform}' from user.platform_prefs[{day}]")

                # ✅ Remove from session.platform_preference
                if session and session.platform_preference and matched_platform in session.platform_preference:
                    session.platform_preference.remove(matched_platform)
                    flag_modified(session, "platform_preference")
                    print(f"🧹 Removed rejected platform '{matched_platform}' from session.platform_preference")

                continue

            # ✅ Try genre match
            matched_genre = await get_best_genre_match(input_genre=tag_clean, db=db)
            if matched_genre:
                if matched_genre not in user.reject_tags["genre"]:
                    user.reject_tags["genre"].append(matched_genre)
                if matched_genre not in reject_data["genre"]:
                    reject_data["genre"].append(matched_genre)
                print(f"✅ Genre matched: {tag_clean} → {matched_genre}")

                # ✅ Remove from user.genre_prefs
                for day, genres in user.genre_prefs.items():
                    if matched_genre in genres:
                        genres.remove(matched_genre)
                        print(f"🧹 Removed rejected genre '{matched_genre}' from user.genre_prefs[{day}]")

                # ✅ Remove from session.genre
                if session and session.genre and matched_genre in session.genre:
                    session.genre.remove(matched_genre)
                    flag_modified(session, "genre")
                    print(f"🧹 Removed rejected genre '{matched_genre}' from session.genre")

                continue

            # ✅ If no match, store in "other"
            if tag_clean not in user.reject_tags["other"]:
                user.reject_tags["other"].append(tag_clean)
            if tag_clean not in reject_data["other"]:
                reject_data["other"].append(tag_clean)
            print(f"⚠️ No match found for: {tag_clean} → added to 'other'")
        flag_modified(session, "meta_data")
        user.last_updated["reject_tags"] = str(datetime.utcnow())

    db.commit()
    await update_game_feedback_from_json(db=db, user_id=user.user_id, session=session, feedback_data=game_feedback)

    session_memory = SessionMemory(session)
    session_memory.update(**classification)