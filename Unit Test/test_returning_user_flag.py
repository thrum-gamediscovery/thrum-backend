
from datetime import datetime, timedelta
from unittest.mock import MagicMock

# Simulated model and enum
class Session:
    def __init__(self, user_id, start_time, end_time, state, meta_data=None):
        self.user_id = user_id
        self.start_time = start_time
        self.end_time = end_time
        self.state = state
        self.meta_data = meta_data or {}
        self.interactions = []

class SessionTypeEnum:
    ONBOARDING = "onboarding"
    ACTIVE = "active"

# Logic to test
def update_returning_user_flag(session):
    if session.meta_data.get("returning_user") is None:
        if session.meta_data.get("last_interaction"):
            session.meta_data["returning_user"] = True
        else:
            session.meta_data["returning_user"] = False

# Mock DB session
class MockDB:
    def __init__(self):
        self.sessions = []

    def query(self, model):
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.sessions[-1] if self.sessions else None

    def add(self, session):
        self.sessions.append(session)

    def commit(self):
        pass

    def refresh(self, session):
        pass

class MockUser:
    def __init__(self, user_id):
        self.user_id = user_id

# Test cases
def test_session_first_time():
    db = MockDB()
    user = MockUser(user_id=1)
    session = Session(
        user_id=user.user_id,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        state=SessionTypeEnum.ONBOARDING,
        meta_data={}
    )
    db.add(session)
    session = db.first()
    update_returning_user_flag(session)
    assert session.meta_data["returning_user"] is False
    print("✅ First-time user test passed")

def test_session_returning():
    db = MockDB()
    user = MockUser(user_id=1)
    session = Session(
        user_id=user.user_id,
        start_time=datetime.utcnow() - timedelta(days=1),
        end_time=datetime.utcnow() - timedelta(days=1),
        state=SessionTypeEnum.ACTIVE,
        meta_data={"last_interaction": datetime.utcnow().isoformat()}
    )
    db.add(session)
    session = db.first()
    update_returning_user_flag(session)
    assert session.meta_data["returning_user"] is True
    print("✅ Returning user test passed")

test_session_first_time()
test_session_returning()
