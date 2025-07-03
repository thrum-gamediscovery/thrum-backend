from app.services.session_memory import confirm_input_summary
from app.db.models.enums import PhaseEnum

async def handle_confirmation(session):
    return await confirm_input_summary(session)
