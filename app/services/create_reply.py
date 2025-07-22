from app.services.thrum_router.phase_intro import handle_intro
from app.services.thrum_router.phase_confirmation import handle_confirmation
from app.services.thrum_router.phase_delivery import handle_delivery
from app.services.thrum_router.phase_followup import handle_followup
from app.services.thrum_router.phase_ending import handle_ending
from app.services.thrum_router.interrupt_logic import check_intent_override
from app.services.input_classifier import classify_user_input
from app.services.user_profile_update import update_user_from_classification
from app.services.session_manager import detect_tone_shift
from app.utils.error_handler import safe_call
from app.utils.repetition_detector import repetition_detector
from app.db.models.session import Session
from app.db.models.enums import PhaseEnum
from app.services.tone_engine import detect_tone_cluster, update_tone_in_history
import random

# Fallback responses when repetition is detected
REPETITION_FALLBACKS = [
    "Let me try a different approach. What kind of game experience are you looking for right now?",
    "I think we're going in circles. Let's reset - what mood are you in for gaming today?",
    "Hmm, let me switch gears. Tell me about your ideal gaming session right now.",
    "Let's try something new. What's your gaming vibe at the moment?",
    "I feel like I'm repeating myself. Let's start fresh - what are you in the mood to play?"
]

@safe_call()
async def generate_thrum_reply(db: Session, user_input: str, session, user, intrection) -> str:
    from app.services.thrum_router.phase_discovery import handle_discovery
    
    session_id = str(session.session_id)
    
    # 🔥 Intent override (e.g., "just give me a game")
    classification = await classify_user_input(session=session, user_input=user_input)
    await update_user_from_classification(db=db, user=user, classification=classification, session=session)
    
    tone = await detect_tone_cluster(user_input)
    update_tone_in_history(session, tone)
    session.meta_data["tone"] = tone

    if detect_tone_shift(session):
        session.tone_shift_detected = True
        db.commit()

    override_reply = await check_intent_override(db=db, user_input=user_input, user=user, session=session, classification=classification, intrection=intrection)
    if override_reply and override_reply is not None:
        # Check for repetition in override replies
        if repetition_detector.is_repetitive(session_id, override_reply):
            if repetition_detector.should_allow_reset(session_id):
                repetition_detector.reset_history(session_id)
                # Reset to discovery phase to break the loop
                session.phase = PhaseEnum.DISCOVERY
                session.game_rejection_count = 0
                db.commit()
                fallback = random.choice(REPETITION_FALLBACKS)
                repetition_detector.add_response(session_id, fallback)
                return fallback
        
        repetition_detector.add_response(session_id, override_reply)
        return override_reply

    phase = session.phase
    
    # Generate response based on current phase
    response = None
    if phase == PhaseEnum.INTRO:
        response = await handle_intro(session)
    elif phase == PhaseEnum.DISCOVERY:
        response = await handle_discovery(db=db, session=session, user=user)
    elif phase == PhaseEnum.CONFIRMATION:
        response = await handle_confirmation(session)
    elif phase == PhaseEnum.DELIVERY:
        response = await handle_delivery(db=db, session=session, user=user, classification=classification, user_input=user_input)
    elif phase == PhaseEnum.FOLLOWUP:
        response = await handle_followup(db=db, session=session, user=user, user_input=user_input, classification=classification, intrection=intrection)
    elif phase == PhaseEnum.ENDING:
        response = await handle_ending(session)
    else:
        response = "Hmm, something went wrong. Let's try again!"
    
    # Check for repetition in phase-based responses
    if repetition_detector.is_repetitive(session_id, response):
        if repetition_detector.should_allow_reset(session_id):
            repetition_detector.reset_history(session_id)
            # Reset to discovery phase to break the loop
            session.phase = PhaseEnum.DISCOVERY
            session.game_rejection_count = 0
            db.commit()
            fallback = random.choice(REPETITION_FALLBACKS)
            repetition_detector.add_response(session_id, fallback)
            return fallback
    
    repetition_detector.add_response(session_id, response)
    return response
