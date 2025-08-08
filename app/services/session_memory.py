# from app.db.models.game import Game
# from app.db.models.game_recommendations import GameRecommendation

# # At the top of app/services/session_memory.py

# def get_game_title_by_id(game_id, db):
#         # Fetch game by ID from the database session
#         game = db.query(Game).filter(Game.game_id == game_id).first()
#         return game.title if game else "Unknown"

# class SessionMemory:
#     def __init__(self, session, db):
#         # Initialize from DB session object; can expand as needed
#         self.user_name = getattr(session.user, "name", None) if hasattr(session, "user") and session.user and session.user.name else ""
#         self.region = getattr(session.user, "region", None) if hasattr(session, "user") and session.user and session.user.region else ""
#         self.mood = getattr(session, "exit_mood", None)
#         self.tone = getattr(session, "meta_data").get("tone")
#         self.genre = session.genre[-1] if session.genre else None
#         self.platform = session.platform_preference[-1] if session.platform_preference else None
#         self.story_preference = getattr(session, "story_preference", None)
#         rejected_ids = getattr(session, "rejected_games", [])
#         self.rejections = [
#             get_game_title_by_id(game_id, db) for game_id in rejected_ids
#         ]
#         rec_ids = [rec.game_id for rec in db.query(GameRecommendation).filter(GameRecommendation.session_id == session.session_id).all()]
#         self.rec_ids = rec_ids
#         self.recommended_game = [
#             get_game_title_by_id(game_id, db) for game_id in rec_ids
#         ]
#         self.likes = getattr(session, "liked_games", []) if hasattr(session, "liked_games") else []
#         self.last_game = getattr(session, "last_recommended_game", None)
#         self.last_intent = getattr(session, "last_intent", None)
#         self.history = [(i.sender.name, i.content, i.tone_tag) for i in getattr(session, "interactions", [])]
#         self.gameplay_elements = getattr(session, "gameplay_elements", None)
#         self.preferred_keywords = getattr(session, "preferred_keywords", None)
#         self.disliked_keywords = getattr(session, "disliked_keywords", None)

#     def update(self, **kwargs):
#         for k, v in kwargs.items():
#             if hasattr(self, k):
#                 setattr(self, k, v)
    
#     def flush(self):
#         self.user_name = ""
#         self.region = ""
#         self.mood = None
#         self.genre = None
#         self.platform = None
#         self.story_preference = None
#         self.tone = None
#         self.rejections = []
#         self.likes = []
#         self.last_game = None
#         self.last_intent = None
#         self.history = []

#     def to_prompt(self):
#         # Summarize memory into a context string for LLM system prompt
#         out = []
#         if self.user_name:
#             out.append(f"User's name: {self.user_name}")
#         if self.region:
#             out.append(f"User lives in : {self.region}")
#         if self.mood:
#             out.append(f"The user’s tone is '{self.tone}' and mood is '{self.mood}'")
#         if self.genre:
#             out.append(f"user likes to play games of {self.genre} genres")
#         if self.platform:
#             out.append(f"user prefer games on {self.platform} platform")
#         if self.story_preference is not None:
#             out.append(f"user {'likes' if self.story_preference else 'does not like '} story driven")
#         if self.gameplay_elements:
#             out.append(f"user likes to play {', '.join(self.gameplay_elements)}")
#         if self.preferred_keywords:
#             out.append(f"user want to play game like {', '.join(self.preferred_keywords)}")
#         if self.disliked_keywords:
#             out.append(f"user hate to game which is like {', '.join(self.disliked_keywords)}")
#         if self.rejections:
#             out.append(f"User rejected these games: {self.rejections}")
#         if self.likes:
#             out.append(f"User Liked games: {self.likes}")
#         if self.last_game:
#             out.append(f"Last game suggested by thrum: {self.last_game}")
#         if self.recommended_game:
#             out.append(f"Thrum already suggested/Recommended {self.recommended_game} games till now to user.")
#         if self.history:
#             last_few = self.history[-10:]
#             hist_str = " | ".join([f"{s} says {c} .. in tone - {t}" for s, c, t in last_few])
#             out.append(f"Recent chat: {hist_str}")

#         return " | ".join(out)


from app.db.models.game import Game
from app.db.models.game_recommendations import GameRecommendation
from sqlalchemy.orm import Session

# ---------- helpers ----------
def get_game_title_by_id(game_id, db: Session):
    game = db.query(Game).filter(Game.game_id == game_id).first()
    return game.title if game else "Unknown"

def _get_titles_by_ids(ids, db: Session):
    if not ids:
        return []
    rows = db.query(Game).filter(Game.game_id.in_(ids)).all()
    by_id = {g.game_id: g.title for g in rows}
    return [by_id.get(i, "Unknown") for i in ids]

def _dedup(seq):
    seen, out = set(), []
    for x in seq or []:
        s = str(x).strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out

def _clip(seq, n):
    seq = _dedup(seq)
    return seq[:n]

def _platform_human(p):
    if not p:
        return None
    name = getattr(p, "name", None) or str(p)
    name = name.replace("_", " ").strip()
    low = name.lower()
    # normalize common cases
    if low in ("ios", "iphone", "iphone / ipod touch", "mobile"):
        return "iPhone"
    if low == "pc":
        return "PC"
    return name.title()

def _shorten(text, max_len=120):
    t = (text or "").replace("\n", " ").strip()
    return t if len(t) <= max_len else (t[: max_len - 1] + "…")

# ---------- main ----------
class SessionMemory:
    def __init__(self, session, db: Session):
        # Basic profile
        user = getattr(session, "user", None)
        self.user_name = getattr(user, "name", "") or ""
        self.region = getattr(user, "region", "") or ""

        # Tone/mood
        self.mood = getattr(session, "exit_mood", None)
        md = getattr(session, "meta_data", {}) or {}
        self.tone = md.get("tone")

        # Prefs
        self.genre = (session.genre or [])[-1] if getattr(session, "genre", None) else None
        self.platform = (session.platform_preference or [])[-1] if getattr(session, "platform_preference", None) else None
        self.story_preference = getattr(session, "story_preference", None)

        # Rejections (ids -> titles)
        rejected_ids = getattr(session, "rejected_games", []) or []
        self.rejections = _get_titles_by_ids(rejected_ids, db)

        # Recommended in this session (ids -> titles)
        rec_ids = [r.game_id for r in db.query(GameRecommendation)
                   .filter(GameRecommendation.session_id == session.session_id)
                   .all()]
        self.rec_ids = rec_ids
        self.recommended_game = _get_titles_by_ids(rec_ids, db)

        # Likes (use session.liked_games if present; otherwise empty)
        self.likes = _dedup(getattr(session, "liked_games", []) if hasattr(session, "liked_games") else [])

        # Last bits
        self.last_game = getattr(session, "last_recommended_game", None)
        self.last_intent = getattr(session, "last_intent", None)

        # History (store but we’ll output only a short window)
        self.history = [(i.sender.name, i.content, getattr(i, "tone_tag", None))
                        for i in getattr(session, "interactions", [])]

        # Optional preference fields
        self.gameplay_elements = getattr(session, "gameplay_elements", None)
        self.preferred_keywords = getattr(session, "preferred_keywords", None)
        self.disliked_keywords = getattr(session, "disliked_keywords", None)

        # Remove contradictions: accepted vs rejected
        if self.likes and self.rejections:
            like_set = set(self.likes)
            self.rejections = [t for t in self.rejections if t not in like_set]

    def update(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def flush(self):
        self.user_name = ""
        self.region = ""
        self.mood = None
        self.genre = None
        self.platform = None
        self.story_preference = None
        self.tone = None
        self.rejections = []
        self.likes = []
        self.last_game = None
        self.last_intent = None
        self.history = []

    def to_prompt(self):
        """
        Compact, grammar-clean, and clipped memory string.
        Avoids contradictions and keeps recent chat short.
        """
        out = []

        # Basics
        if self.user_name:
            out.append(f"User's name: {self.user_name}")
        if self.region:
            out.append(f"User lives in: {self.region}")

        # Tone/Mood
        tone_bits = []
        if self.tone:
            tone_bits.append(f"tone is '{self.tone}'")
        if self.mood:
            tone_bits.append(f"mood is '{self.mood}'")
        if tone_bits:
            out.append(f"The user's " + " and ".join(tone_bits))

        # Prefs
        if self.genre:
            out.append(f"Likes genres: {self.genre}")
        if self.platform:
            out.append(f"Primary platform: {_platform_human(self.platform)}")
        if self.story_preference is not None:
            out.append("Story preference: likes story-driven" if self.story_preference
                       else "Story preference: not story-driven")

        if self.gameplay_elements:
            out.append("Gameplay vibes: " + ", ".join(_clip(self.gameplay_elements, 6)))
        if self.preferred_keywords:
            out.append("Wants games like: " + ", ".join(_clip(self.preferred_keywords, 10)))
        if self.disliked_keywords:
            out.append("Dislikes: " + ", ".join(_clip(self.disliked_keywords, 6)))

        # Games
        if self.rejections:
            out.append("Rejected: " + ", ".join(_clip(self.rejections, 10)))
        if self.likes:
            out.append("Accepted: " + ", ".join(_clip(self.likes, 10)))
        if self.last_game:
            out.append(f"Last suggested: {self.last_game}")
        if self.recommended_game:
            out.append("Suggested so far: " + ", ".join(_clip(self.recommended_game, 12)))

        # Recent chat (short window)
        if self.history:
            last_few = self.history[-10:]  # clip to last 6 entries
            hist_str = " | ".join([f"{s} says {_shorten(c)}" + (f" .. tone - {t}" if t else "")
                                   for s, c, t in last_few])
            out.append(f"Recent chat: {hist_str}")

        return " | ".join(out)