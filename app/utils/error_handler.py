import traceback

def safe_call(default_reply="Sorry friend, I hit a snag. Want to try that again? 🎮"):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                print(f"[❌ ERROR in {func.__name__}]: {e}")
                traceback.print_exc()
                return default_reply
        return wrapper
    return decorator
