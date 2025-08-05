from app.services.thrum_router.phase_intro import handle_intro
from app.services.thrum_router.phase_confirmation import confirm_input_summary
from app.services.thrum_router.phase_delivery import handle_delivery
from app.services.thrum_router.phase_followup import ask_followup_que
from app.services.thrum_router.phase_ending import handle_ending
from app.services.thrum_router.interrupt_logic import check_intent_override
from app.services.input_classifier import classify_user_input
from app.services.user_profile_update import update_user_from_classification
from app.services.session_manager import detect_tone_shift
from app.utils.error_handler import safe_call
from app.db.models.session import Session
from app.db.models.enums import PhaseEnum
from app.services.tone_shift_detection import emotion_fusion

@safe_call()
async def generate_thrum_reply(db: Session, user_input: str, session, user, intrection) -> str:
    from app.services.thrum_router.phase_discovery import handle_discovery
    # 🔥 Intent override (e.g., "just give me a game")
    classification = await classify_user_input(db=db,session=session, user_input=user_input)
    if isinstance(classification, dict):
        await update_user_from_classification(db=db, user=user, classification=classification, session=session)
    
    fusion = await emotion_fusion(db,session, user)
    if await detect_tone_shift(session):
        session.tone_shift_detected = True
        db.commit()

    override_reply = await check_intent_override(db=db, user_input=user_input, user=user, session=session, classification=classification, intrection=intrection)
    if override_reply and override_reply is not None:
        return override_reply


    phase = session.phase

    if phase == PhaseEnum.INTRO:
        return await handle_intro(session)

    elif phase == PhaseEnum.DISCOVERY:
        return await handle_discovery(db=db, session=session, user=user,user_input=user_input)

    elif phase == PhaseEnum.CONFIRMATION:
        return await confirm_input_summary(db=db,session=session,user=user,user_input=user_input)

    elif phase == PhaseEnum.DELIVERY:
        return await handle_delivery(db=db, session=session, user=user, classification=classification)

    elif phase == PhaseEnum.FOLLOWUP:
        return await ask_followup_que(session=session)

    elif phase == PhaseEnum.ENDING:
        return await handle_ending(session)

    return "Hmm, something went wrong. Let's try again!"
