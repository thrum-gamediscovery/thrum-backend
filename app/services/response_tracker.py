"""
Tracks and prevents repetitive responses.
"""

class ResponseTracker:
    """Prevents repetitive bot responses"""
    
    @staticmethod
    def get_recent_responses(session, limit=3):
        """Get recent Thrum responses"""
        from app.db.models.enums import SenderEnum
        thrum_responses = [
            i.content for i in session.interactions 
            if i.sender == SenderEnum.Thrum
        ]
        return thrum_responses[-limit:] if thrum_responses else []
    
    @staticmethod
    def is_repetitive(new_response, recent_responses):
        """Check if response is too similar to recent ones"""
        if not recent_responses:
            return False
        
        # Simple similarity check
        new_words = set(new_response.lower().split())
        for recent in recent_responses:
            recent_words = set(recent.lower().split())
            overlap = len(new_words & recent_words)
            if overlap > len(new_words) * 0.7:  # 70% word overlap
                return True
        return False
    
    @staticmethod
    def add_variation(base_response):
        """Add variation to prevent repetition"""
        variations = [
            "Actually, ",
            "Hmm, ",
            "Let me think... ",
            "You know what, ",
            "Here's the thing - "
        ]
        import random
        return random.choice(variations) + base_response.lower()