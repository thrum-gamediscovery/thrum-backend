
from datetime import datetime, timedelta

# Simulated Session class for test
class Session:
    def __init__(self, user_id, start_time, end_time=None, meta_data=None):
        self.user_id = user_id
        self.start_time = start_time
        self.end_time = end_time or start_time
        self.meta_data = meta_data or {}
        self.interactions = []

# Reengagement flag updater
def update_returning_user_flag(session):
    if session.meta_data.get("returning_user") is None:
        if session.meta_data.get("last_interaction"):
            session.meta_data["returning_user"] = True
        else:
            session.meta_data["returning_user"] = False

# Simulate returning logic
def simulate_user_return(now, last_interaction_iso):
    session = Session(
        user_id=1,
        start_time=now - timedelta(hours=1),
        end_time=now - timedelta(hours=1),
        meta_data={
            "last_interaction": last_interaction_iso
        }
    )
    # Apply reengagement logic
    try:
        last_interaction = datetime.fromisoformat(session.meta_data["last_interaction"])
        idle_seconds = (now - last_interaction).total_seconds()
        if idle_seconds > 1800:
            session.meta_data["returning_user"] = True
    except:
        session.meta_data["returning_user"] = False

    update_returning_user_flag(session)
    return session.meta_data["returning_user"]

# Test 1: First-time user (no last_interaction)
def test_first_time_user():
    session = Session(user_id=1, start_time=datetime.utcnow())
    update_returning_user_flag(session)
    assert session.meta_data["returning_user"] is False
    print("✅ Test 1 Passed: First-time user is NOT returning")

# Test 2: Idle > 30 minutes (returning user)
def test_returning_user_idle():
    now = datetime.utcnow()
    past = (now - timedelta(minutes=45)).isoformat()
    assert simulate_user_return(now, past) is True
    print("✅ Test 2 Passed: Returning user detected after 45 min idle")

# Test 3: Idle < 30 minutes (not returning)
def test_active_user():
    now = datetime.utcnow()
    recent = (now - timedelta(minutes=10)).isoformat()
    assert simulate_user_return(now, recent) is False
    print("✅ Test 3 Passed: Active user NOT flagged as returning")

# Run tests
test_first_time_user()
test_returning_user_idle()
test_active_user()
