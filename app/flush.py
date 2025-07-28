from app.db.session import SessionLocal
from app.db.models.session import Session
from app.services.session_memory import SessionMemory

def truncate_users_and_flush_sessions():
    db = SessionLocal()

    try:
        # 🔄 2. Flush all session memory
        sessions = db.query(Session).all()
        for session in sessions:
            memory = SessionMemory(session)
            memory.flush()
        print(f"✅ Flushed memory for {len(sessions)} sessions.")

        # ✅ Commit changes
        db.commit()
        print("🎉 All changes committed successfully.")
    except Exception as e:
        db.rollback()
        print("❌ Error:", e)
    finally:
        db.close()

if __name__ == "__main__":
    truncate_users_and_flush_sessions()