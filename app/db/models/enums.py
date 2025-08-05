"""
Pydantic Enum models for various categories.

These enums are used for validating and categorizing data within request and response schemas.
"""

import enum

class PlatformEnum(str, enum.Enum):
    WhatsApp = "WhatsApp"
    Discord = "Discord"
    Telegram = "Telegram"
    Steam = "Steam"
    Xbox = "Xbox"
    PlayStation = "PlayStation"

class SenderEnum(str, enum.Enum):
    User = "User"
    Thrum = "Thrum"

class ResponseTypeEnum(str, enum.Enum):
    GameRec = "GameRec"
    Intro = "Intro"
    DiscoveryQ = "DiscoveryQ"
    Confirmation = "Confirmation"
    Followup = "Followup"
    RejectionAck = "RejectionAck"
    IdleChat = "IdleChat"
    ReEntry = "ReEntry"
    Callback = "Callback"
    MoodlessFallback = "MoodlessFallback"
    IntentOverride = "IntentOverride"
    ExitMessage = "ExitMessage"
    ErrorRecovery = "ErrorRecovery"
    NotInTheMood = "NotInTheMood"
    SharePrompt = "SharePrompt"

class SessionTypeEnum(str, enum.Enum):
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    PASSIVE = "passive"
    COLD = "cold"
    CLOSED = "closed"

class PhaseEnum(str, enum.Enum):
    INTRO = "intro"
    DISCOVERY = "discovery"
    CONFIRMATION = "confirmation"
    DELIVERY = "delivery"
    FOLLOWUP = "followup"
    ENDING = "ending"