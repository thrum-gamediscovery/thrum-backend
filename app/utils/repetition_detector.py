"""
Utility for detecting repetitive responses in conversations.
Helps prevent the chatbot from getting stuck in loops.
"""

from typing import Dict, List
from datetime import datetime, timedelta
import difflib

class RepetitionDetector:
    def __init__(self, max_history: int = 5, similarity_threshold: float = 0.8):
        self.max_history = max_history
        self.similarity_threshold = similarity_threshold
        self.response_history: Dict[str, List[str]] = {}
        self.last_reset: Dict[str, datetime] = {}
    
    def is_repetitive(self, session_id: str, response: str) -> bool:
        """
        Check if the current response is too similar to recent responses.
        Returns True if repetition is detected.
        """
        if session_id not in self.response_history:
            self.response_history[session_id] = []
            self.last_reset[session_id] = datetime.utcnow()
            return False
        
        # Check similarity with recent responses
        for prev_response in self.response_history[session_id]:
            similarity = self._calculate_similarity(response, prev_response)
            if similarity > self.similarity_threshold:
                return True
        
        return False
    
    def add_response(self, session_id: str, response: str) -> None:
        """Add a response to the history."""
        if session_id not in self.response_history:
            self.response_history[session_id] = []
            self.last_reset[session_id] = datetime.utcnow()
        
        self.response_history[session_id].append(response)
        
        # Keep only the most recent responses
        if len(self.response_history[session_id]) > self.max_history:
            self.response_history[session_id].pop(0)
    
    def reset_history(self, session_id: str) -> None:
        """Reset the response history for a session."""
        self.response_history[session_id] = []
        self.last_reset[session_id] = datetime.utcnow()
    
    def should_allow_reset(self, session_id: str) -> bool:
        """
        Check if enough time has passed since the last reset.
        Prevents too frequent resets.
        """
        if session_id not in self.last_reset:
            return True
        
        # Allow reset if at least 2 minutes have passed
        return datetime.utcnow() - self.last_reset[session_id] > timedelta(minutes=2)
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using difflib."""
        return difflib.SequenceMatcher(None, text1, text2).ratio()

# Global instance
repetition_detector = RepetitionDetector()