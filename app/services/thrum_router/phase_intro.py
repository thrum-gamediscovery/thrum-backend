from app.db.models.enums import PhaseEnum
from app.services.dynamic_response_engine import generate_dynamic_response

async def handle_intro(session):
    user = session.user
    return await generate_dynamic_response(user, session, phase='greeting')