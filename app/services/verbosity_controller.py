"""
Verbosity Controller - Manages response length based on user behavior and requests
"""

import re
from typing import Tuple

def detect_verbosity_request(user_input: str) -> Tuple[str, bool]:
    """
    Detect if user is requesting more or less detail.
    Returns (verbosity_level, is_request)
    """
    if not user_input:
        return "short", False
    
    input_lower = user_input.lower().strip()
    
    # Patterns for requesting more detail
    more_patterns = [
        r'\b(want more|tell me more|give me more|more detail|expand|elaborate)\b',
        r'\b(want to hear more|wanna know more|say more)\b',
        r'\b(go deeper|dive deeper|more info)\b',
        r'\b(longer|detailed|full story)\b'
    ]
    
    # Patterns for requesting less detail  
    less_patterns = [
        r'\b(too long|too much|shorter|brief|quick)\b',
        r'\b(keep it short|make it brief|tldr|tl;dr)\b',
        r'\b(just the basics|simple|concise)\b'
    ]
    
    # Check for more detail requests
    for pattern in more_patterns:
        if re.search(pattern, input_lower):
            return "long", True
    
    # Check for less detail requests
    for pattern in less_patterns:
        if re.search(pattern, input_lower):
            return "short", True
    
    return "short", False

def update_session_verbosity(session, verbosity_level: str):
    """Update session metadata with new verbosity preference"""
    session.meta_data = session.meta_data or {}
    session.meta_data["verbosity"] = verbosity_level
    
    # Track verbosity changes for analytics
    verbosity_history = session.meta_data.get("verbosity_history", [])
    verbosity_history.append(verbosity_level)
    session.meta_data["verbosity_history"] = verbosity_history[-5:]  # Keep last 5 changes

def get_length_instruction(verbosity: str) -> str:
    """Get prompt instruction based on verbosity level"""
    instructions = {
        "short": "Keep response to 1-2 sentences maximum. Be concise and direct.",
        "normal": "Keep response moderate length, around 2-3 sentences.",
        "long": "Provide detailed response with full context and explanation."
    }
    return instructions.get(verbosity, instructions["short"])

def should_add_followup(verbosity: str, tone: str) -> bool:
    """Determine if 'want more?' followup should be added"""
    if verbosity == "long":
        return False  # Already detailed
    
    # Add followup for engaged tones when response is short
    engaged_tones = {"warm", "enthusiastic", "excited", "friendly", "playful", "curious"}
    return tone in engaged_tones

def generate_followup_prompt(tone: str) -> str:
    """Generate tone-matched followup prompt"""
    followups = {
        "warm": "Want me to go deeper? 🤗",
        "enthusiastic": "Wanna hear more? 🎉", 
        "excited": "Want the full story? ✨",
        "friendly": "Want more details? 😊",
        "playful": "Curious for more? 😜",
        "curious": "Want me to elaborate? 🤔",
        "casual": "Want more? 👋",
        "neutral": "Want more info?",
        "cheerful": "Want the full scoop? 😄"
    }
    return followups.get(tone, "Want more?")