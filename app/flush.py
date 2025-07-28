# flush.py

from app.services.session_memory import session_memory

def flush_all_memory():
    session_memory.clear()
    print("✅ All session memory and locks have been cleared.")

if __name__ == "__main__":
    flush_all_memory()
