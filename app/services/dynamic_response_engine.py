from app.services.smart_conversation_engine import SmartConversationEngine

def generate_fallback_response(user_input: str, user, session) -> str:
    """Generate rule-based responses when AI fails"""
    user_input_lower = user_input.lower().strip()
    
    # Greeting responses
    if any(word in user_input_lower for word in ['hello', 'hi', 'hey', 'start']):
        name = f" {user.name}" if user.name else ""
        return f"Hey there{name}! 😊 I'm Thrum, your game buddy. What kind of vibe are you going for today?"
    
    # Mood-based responses
    if any(word in user_input_lower for word in ['chill', 'relax', 'calm']):
        return "Nice! For a chill vibe, I'd suggest Stardew Valley or Animal Crossing. What platform do you prefer? 🎮"
    
    if any(word in user_input_lower for word in ['action', 'intense', 'fast']):
        return "Awesome! For some action, try Hades or Celeste. They're both incredible! What do you think? 🔥"
    
    if any(word in user_input_lower for word in ['story', 'narrative', 'emotional']):
        return "Great choice! For amazing stories, check out Life is Strange or What Remains of Edith Finch. Sound good? 📚"
    
    # Platform questions
    if any(word in user_input_lower for word in ['pc', 'computer', 'steam']):
        return "PC gaming! 💻 What genre gets you excited? RPG, action, indie, or something else?"
    
    if any(word in user_input_lower for word in ['mobile', 'phone']):
        return "Mobile gaming! 📱 Are you looking for something quick and casual, or a deeper experience?"
    
    # Generic game request
    if any(word in user_input_lower for word in ['game', 'recommend', 'suggest']):
        return "I'd love to help! Tell me your current mood - are you feeling chill, hyped, creative, or something else? 🌈"
    
    # Default response
    return "I'm here to help you discover amazing games! What's your vibe today - chill, action-packed, or maybe something creative? 🎲"

async def generate_dynamic_response(user, session, user_input: str = "", phase: str = None, db=None) -> str:
    """Generate smart responses using GPT-powered conversation engine"""
    print(f"🚀 generate_dynamic_response called with input: {user_input}")
    
    try:
        engine = SmartConversationEngine(user, session, db)
        response = await engine.process_conversation(user_input)
        print(f"🎆 SmartConversationEngine returned: {response}")
        return response
    except Exception as e:
        print(f"❌ Smart conversation error: {e}")
        print(f"🔄 Falling back to rule-based response")
        # Fallback to rule-based responses
        fallback = generate_fallback_response(user_input, user, session)
        print(f"🔙 Fallback response: {fallback}")
        return fallback