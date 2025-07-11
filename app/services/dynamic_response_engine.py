from app.services.smart_conversation_engine import SmartConversationEngine

async def generate_dynamic_response(user, session, user_input: str = "", phase: str = None, db=None) -> str:
    """Generate smart responses using GPT-powered conversation engine"""
    try:
        engine = SmartConversationEngine(user, session, db)
        response = await engine.process_conversation(user_input)
        return response
    except Exception as e:
        print(f"Smart conversation error: {e}")
        return "Hey! I'm Thrum, your game discovery buddy. What's on your mind today? 🎮"