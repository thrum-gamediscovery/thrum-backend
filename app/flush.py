from app.db.session import SessionLocal
from app.db.models.session import Session
from app.services.session_memory import SessionMemory

def flush_all_session_memory():
    db = SessionLocal()

    try:
        sessions = db.query(Session).all()
        for session in sessions:
            memory = SessionMemory(session,db)
            memory.flush()
        print(f"✅ Flushed memory for {len(sessions)} sessions.")

        db.commit()
        print("🎉 All changes committed successfully.")

    except Exception as e:
        db.rollback()
        print("❌ Error:", e)

    finally:
        db.close()

if __name__ == "__main__":
    flush_all_session_memory()
