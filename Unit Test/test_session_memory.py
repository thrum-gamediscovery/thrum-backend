import pytest
from app.services.session_memory import SessionMemory

class DummyUser:
    def __init__(self, name=None):
        self.name = name

class DummySession:
    def __init__(self):
        self.user = DummyUser("Avinash")
        self.exit_mood = "chill"
        self.genre = ["builder"]
        self.platform_preference = ["Android"]
        self.story_preference = True
        self.last_tone = "excited"
        self.rejected_games = ["GTA"]
        self.liked_games = ["Minecraft"]
        self.last_recommended_game = "Pocket Build"
        self.last_intent = "Request_Quick_Recommendation"
        self.interactions = []

def test_session_memory_to_prompt():
    session = DummySession()
    memory = SessionMemory(session)
    result = memory.to_prompt()
    assert "User name: Avinash" in result
    assert "Mood: chill" in result
    assert "Genre: builder" in result
    assert "Platform: Android" in result
    assert "Story preference: Yes" in result
    assert "Rejected games: ['GTA']" in result
    assert "Liked games: ['Minecraft']" in result
    assert "Last game suggested: Pocket Build" in result
    assert "Last intent: Request_Quick_Recommendation" in result

def test_session_memory_update():
    session = DummySession()
    memory = SessionMemory(session)
    memory.update(mood="hyped", genre="action", platform="iOS", last_game="Clash Royale")
    assert memory.mood == "hyped"
    assert memory.genre == "action"
    assert memory.platform == "iOS"
    assert memory.last_game == "Clash Royale"
