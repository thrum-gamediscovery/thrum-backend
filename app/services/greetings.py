import random

async def generate_intro(is_first_message: bool, idle_reconnect: bool, user_input: str, user=None) -> str:
    name = getattr(user, "name", None) if user else None
    
    # Detect user's tone from input for matching
    user_tone = "casual"
    if any(word in user_input.lower() for word in ["hey", "heyy", "yo", "sup"]):
        user_tone = "casual"
    elif any(word in user_input.lower() for word in ["hello", "hi", "good"]):
        user_tone = "friendly"
    elif "lol" in user_input.lower() or "😄" in user_input or "😂" in user_input:
        user_tone = "playful"
    
    # Natural intro variations based on examples and user tone
    if is_first_message:
        if user_tone == "playful":
            intros = [
                "Haha I'll take that title 😄 Yep – I'm Thrum, and I help people find games that fit their mood, not just their genre. Want a little rec to start?",
                "Hey 👋 I'm Thrum – I help people find games that match their mood. Want a quick rec? Totally chill if not. 😎"
            ]
        elif user_tone == "casual":
            intros = [
                "Hey 👋 I'm Thrum – I help people find games that actually fit their vibe. Want a quick recommendation? No pressure.",
                "Hey 👋 I'm Thrum – I help people find games that match their mood. Want a quick rec? Totally optional, no strings 😎"
            ]
        else:
            intros = [
                "Hey 👋 Nice to meet you. I'm Thrum – I help people find games that actually fit their mood. Want a quick recommendation? No pressure.",
                "Hey 👋 I'm Thrum – I help people find games that match their mood. Want a quick rec? Totally chill if not. 😎"
            ]
        return random.choice(intros)
    
    # For returning users with name - personalized greetings
    if name and not is_first_message:
        if idle_reconnect:
            return f"Hey {name} 👋 Back for more game recs? What's the vibe today?"
        else:
            return f"Nice to meet you properly, {name} 🙌"
    
    # Returning users without name
    if not is_first_message and not name:
        return "Hey again 👋 Ready for another game rec?"
    
    # Fallback
    return "Hey 👋 I'm Thrum – I help people find games that match your vibe. Want a quick rec?"