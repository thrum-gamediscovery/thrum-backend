from app.services.thrum_router.phase_intro import handle_intro
from app.services.thrum_router.phase_discovery import handle_discovery
from app.services.thrum_router.phase_confirmation import handle_confirmation
from app.services.thrum_router.phase_delivery import handle_delivery
from app.services.thrum_router.phase_followup import handle_followup
from app.services.thrum_router.interrupt_logic import check_intent_override
from app.db.models.session import Session


from app.db.models.enums import PhaseEnum

async def generate_thrum_reply(db:Session, user_input: str, session, user) -> str:
    # 🔥 Intent override (e.g., "just give me a game")
    override_reply = await check_intent_override(db, user_input, user, session)
    if override_reply:
        return override_reply

    phase = session.phase

    if phase == PhaseEnum.INTRO:
        return await handle_intro(session, is_first_message=True, idle_reconnect=False, user_input=user_input)

    elif phase == PhaseEnum.DISCOVERY:
        return await handle_discovery(db, user_input, session, user)

    elif phase == PhaseEnum.CONFIRMATION:
        return await handle_confirmation(session)

    elif phase == PhaseEnum.DELIVERY:
        return await handle_delivery(db, session, user)

    elif phase == PhaseEnum.FOLLOWUP:
        return await handle_followup(user_input, session, user)

    return "Hmm, something went wrong. Let’s try again!"
