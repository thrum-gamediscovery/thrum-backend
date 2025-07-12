"""
Configuration for natural conversation system
"""

# OpenAI Configuration
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TEMPERATURE = 0.8
OPENAI_MAX_TOKENS = 150

# Conversation Flow Settings
CONVERSATION_MEMORY_LIMIT = 8  # Number of recent interactions to remember
CONTEXT_ANALYSIS_DEPTH = 4     # Number of messages to analyze for context
RECOMMENDATION_CONFIDENCE_THRESHOLD = 0.6  # Minimum confidence to recommend

# Response Style Settings
RESPONSE_LENGTH_TARGET = 50    # Target response length in words
EMOJI_USAGE_LEVEL = "moderate" # low, moderate, high
PERSONALITY_ADAPTATION = True  # Adapt to user's communication style

# User Preference Confidence Levels
MOOD_CONFIDENCE_THRESHOLD = 0.7
GENRE_CONFIDENCE_THRESHOLD = 0.6
PLATFORM_CONFIDENCE_THRESHOLD = 0.5

# Interaction Tracking
TRACK_USER_PATTERNS = True
ANALYZE_CONVERSATION_FLOW = True
ADAPTIVE_RESPONSES = True

# Fallback Settings
USE_RULE_BASED_FALLBACK = True
FALLBACK_TIMEOUT_SECONDS = 5

# Debug Settings
ENABLE_CONVERSATION_LOGGING = True
LOG_ANALYSIS_RESULTS = True