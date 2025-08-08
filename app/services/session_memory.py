from app.db.models.game import Game
from app.db.models.game_recommendations import GameRecommendation

# At the top of app/services/session_memory.py

def get_game_title_by_id(game_id, db):
        # Fetch game by ID from the database session
        game = db.query(Game).filter(Game.game_id == game_id).first()
        return game.title if game else "Unknown"

class SessionMemory:
    def __init__(self, session, db):
        # Initialize from DB session object; can expand as needed
        self.user_name = getattr(session.user, "name", None) if hasattr(session, "user") and session.user and session.user.name else ""
        self.region = getattr(session.user, "region", None) if hasattr(session, "user") and session.user and session.user.region else ""
        self.mood = getattr(session, "exit_mood", None)
        self.tone = getattr(session, "meta_data").get("tone")
        self.genre = session.genre[-1] if session.genre else None
        self.platform = session.platform_preference[-1] if session.platform_preference else None
        self.story_preference = getattr(session, "story_preference", None)
        rejected_ids = getattr(session, "rejected_games", [])
        self.rejections = [
            get_game_title_by_id(game_id, db) for game_id in rejected_ids
        ]
        rec_ids = [rec.game_id for rec in db.query(GameRecommendation).filter(GameRecommendation.session_id == session.session_id).all()]
        self.rec_ids = rec_ids
        self.recommended_game = [
            get_game_title_by_id(game_id, db) for game_id in rec_ids
        ]
        self.likes = getattr(session, "liked_games", []) if hasattr(session, "liked_games") else []
        self.last_game = getattr(session, "last_recommended_game", None)
        self.last_intent = getattr(session, "last_intent", None)
        self.history = [(i.sender.name, i.content, i.tone_tag) for i in getattr(session, "interactions", [])]
        self.gameplay_elements = getattr(session, "gameplay_elements", None)
        self.preferred_keywords = getattr(session, "preferred_keywords", None)
        self.disliked_keywords = getattr(session, "disliked_keywords", None)

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
        # Summarize memory into a context string for LLM system prompt
        out = []
        if self.user_name:
            out.append(f"User's name: {self.user_name}")
        if self.region:
            out.append(f"User lives in : {self.region}")
        if self.mood:
            out.append(f"The user’s tone is '{self.tone}' and mood is '{self.mood}'")
        if self.genre:
            out.append(f"user likes to play games of {self.genre} genres")
        if self.platform:
            out.append(f"user prefer games on {self.platform} platform")
        if self.story_preference is not None:
            out.append(f"user {'likes' if self.story_preference else 'does not like '} story driven")
        if self.gameplay_elements:
            out.append(f"user likes to play {', '.join(self.gameplay_elements)}")
        if self.preferred_keywords:
            out.append(f"user want to play game like {', '.join(self.preferred_keywords)}")
        if self.disliked_keywords:
            out.append(f"user hate to game which is like {', '.join(self.disliked_keywords)}")
        if self.rejections:
            out.append(f"User rejected these games: {self.rejections}")
        if self.likes:
            out.append(f"User Liked games: {self.likes}")
        if self.last_game:
            out.append(f"Last game suggested by thrum: {self.last_game}")
        if self.recommended_game:
            out.append(f"Thrum already suggested/Recommended {self.recommended_game} games till now to user.")
        if self.history:
            last_few = self.history
            hist_str = " | ".join([f"{s} says {c} .. in tone - {t}" for s, c, t in last_few])
            out.append(f"Recent chat: {hist_str}")

        return " | ".join(out)


