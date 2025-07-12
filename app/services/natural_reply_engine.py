from app.services.conversation_manager import create_conversation_manager
from app.utils.error_handler import safe_call

@safe_call("Hey! I'm Thrum, your game discovery buddy. What's your vibe today? 🎮")
async def generate_natural_reply(db, user, session, user_input: str) -> str:
    """
    Main entry point for natural conversation processing
    Replaces the complex phase-based system with natural flow
    """
    print(f"🎯 Natural Reply Engine processing: {user_input}")
    
    # Create conversation manager
    conversation_manager = await create_conversation_manager(user, session, db)
    
    # Process conversation naturally
    reply = await conversation_manager.process_conversation(user_input)
    
    print(f"✅ Natural reply generated: {reply}")
    return reply