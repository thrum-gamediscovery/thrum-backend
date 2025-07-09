from app.services.thrum_router.phase_intro import handle_intro
from app.services.thrum_router.phase_discovery import handle_discovery
from app.services.thrum_router.phase_confirmation import handle_confirmation
from app.services.thrum_router.phase_delivery import handle_delivery
from app.services.thrum_router.phase_followup import handle_followup
from app.services.thrum_router.phase_ending import handle_ending
from app.services.thrum_router.interrupt_logic import check_intent_override
from app.services.input_classifier import classify_user_input
from app.services.user_profile_update import update_user_from_classification
from app.services.session_manager import detect_tone_shift
from app.utils.error_handler import safe_call
from app.db.models.session import Session
from app.db.models.enums import PhaseEnum
from app.services.tone_engine import detect_tone_cluster, update_tone_in_history

@safe_call()
async def generate_thrum_reply(db: Session, user_input: str, session, user) -> str:
    # 🔥 Intent override (e.g., "just give me a game")
    classification = await classify_user_input(session=session, user_input=user_input)
    await update_user_from_classification(db=db, user=user, classification=classification, session=session)
    
    tone = await detect_tone_cluster(user_input)
    update_tone_in_history(session, tone)
    session.meta_data["tone"] = tone

    if detect_tone_shift(session):
        session.tone_shift_detected = True
        db.commit()

    override_reply = await check_intent_override(db=db, user_input=user_input, user=user, session=session, classification=classification)
    if override_reply and override_reply is not None:
        return override_reply


    phase = session.phase
    print(f"Current phase:>>>>>>>>>>>>>>>>>>>>>>>>> {phase}")

    if phase == PhaseEnum.INTRO:
        return await handle_intro()

    elif phase == PhaseEnum.DISCOVERY:
        return await handle_discovery(db=db, session=session, user=user,classification=classification, user_input=user_input)

    elif phase == PhaseEnum.CONFIRMATION:
        return await handle_confirmation(session)

    elif phase == PhaseEnum.DELIVERY:
        return await handle_delivery(db=db, session=session, user=user, classification=classification, user_input=user_input)

    elif phase == PhaseEnum.FOLLOWUP:
        return await handle_followup(db=db, session=session, user=user, user_input=user_input, classification=classification)

    elif phase == PhaseEnum.ENDING:
        return await handle_ending(session)

    return "Hmm, something went wrong. Let's try again!"
