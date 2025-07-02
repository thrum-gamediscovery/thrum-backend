from app.services.game_recommend import game_recommendation
from app.services.session_memory import format_game_output
from app.db.models.enums import PhaseEnum
from app.db.models.session import Session

async def handle_delivery(db:Session, session, user):
    game,_ = await game_recommendation(db=db, user=user, session=session)
    session.last_recommended_game = game["title"] 
    session.phase = PhaseEnum.FOLLOWUP
    return await format_game_output(game)
