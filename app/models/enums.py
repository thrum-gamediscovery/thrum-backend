"""
Pydantic Enum models for various categories.

These enums are used for validating and categorizing data within request and response schemas.
"""

import enum

class PlatformEnum(str, enum.Enum):
    WhatsApp = "WhatsApp"
    Discord = "Discord"
    Telegram = "Telegram"

class SenderEnum(str, enum.Enum):
    User = "User"
    Thrum = "Thrum"

class ResponseTypeEnum(str, enum.Enum):
    GameRec = "GameRec"
    Callback = "Callback"
    ReEntry = "ReEntry"
    IdleChat = "IdleChat"