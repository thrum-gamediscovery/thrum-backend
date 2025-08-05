from app.services.nudge_checker import check_for_nudge
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

scheduler.add_job(check_for_nudge, 'interval', seconds=25, max_instances=2)

def start_scheduler():
    scheduler.start()
def stop_scheduler():
    scheduler.shutdown()