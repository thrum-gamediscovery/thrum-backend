from apscheduler.schedulers.background import BackgroundScheduler
from app.services.nudge_checker import check_for_nudge
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_for_nudge, 'interval', seconds=10)
    scheduler.start()
