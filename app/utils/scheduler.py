from app.services.thrum_router.phase_delivery import recommend_game
from app.services.nudge_checker import get_followup, check_for_nudge
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

scheduler.add_job(check_for_nudge, 'interval', seconds=25, max_instances=2)
scheduler.add_job(recommend_game, 'interval', seconds=5, max_instances=2)
scheduler.add_job(get_followup, 'interval', seconds=7, max_instances=2)

def start_scheduler():
    scheduler.start()
def stop_scheduler():
    scheduler.shutdown()