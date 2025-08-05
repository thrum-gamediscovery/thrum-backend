from app.db.models.interaction import Interaction
from app.db.models.enums import ResponseTypeEnum
from datetime import datetime

def determine_response_type_from_phase(phase: str):
    if phase == "intro":
        return ResponseTypeEnum.Intro
    elif phase == "discovery":
        return ResponseTypeEnum.DiscoveryQ
    elif phase == "delivery":
        return ResponseTypeEnum.GameRec
    elif phase == "followup":
        return ResponseTypeEnum.Followup
    return None

def create_interaction(
    session,
    session_id,
    sender,
    content,
    mood_tag=None,
    tone_tag=None,
    confidence_score=None,
    game_id=None,
    session_type=None,
    bot_response_metadata=None
):
    return Interaction(
        session_id=session_id,
        sender=sender,
        content=content,
        response_type=determine_response_type_from_phase(session.phase),
        mood_tag=mood_tag,
        tone_tag=tone_tag,
        confidence_score=confidence_score,
        game_id=game_id,
        session_type=session_type,
        
        bot_response_metadata=bot_response_metadata or {},
        timestamp=datetime.utcnow()
    )
