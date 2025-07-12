from app.services.create_reply import generate_thrum_reply
from app.utils.error_handler import safe_call

@safe_call("Hey! I'm Thrum, your game discovery buddy. What's your vibe today? 🎮")
async def generate_natural_reply(db, user, session, user_input: str) -> str:
    """
    Main entry point for natural conversation processing
    Uses the simplified Thrum conversation flow
    """
    print(f"🎯 Natural Reply Engine processing: {user_input}")
    
    # Use the simplified Thrum reply generator
    reply = await generate_thrum_reply(db, user, session, user_input)
    
    print(f"✅ Natural reply generated: {reply}")
    return reply