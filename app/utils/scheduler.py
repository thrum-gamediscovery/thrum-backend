import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.nudge_checker import check_for_nudge
from app.services.thrum_router.phase_delivery import recommend_game
from app.services.thrum_router.phase_followup import get_followup
from app.services.thrum_router.phase_confirmation import ask_for_name_if_needed
from app.utils.repetition_detector import repetition_detector
from datetime import datetime, timedelta

scheduler = BackgroundScheduler()
def async_wrapper(coro_func):
    def wrapped():
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(coro_func())
            else:
                loop.run_until_complete(coro_func())
        except RuntimeError:
            asyncio.run(coro_func())
    return wrapped

async def cleanup_repetition_detector():
    """Clean up old session data from the repetition detector"""
    now = datetime.utcnow()
    # Remove sessions older than 24 hours
    expired_sessions = []
    for session_id, last_reset in repetition_detector.last_reset.items():
        if now - last_reset > timedelta(hours=24):
            expired_sessions.append(session_id)
    
    for session_id in expired_sessions:
        if session_id in repetition_detector.response_history:
            del repetition_detector.response_history[session_id]
        if session_id in repetition_detector.last_reset:
            del repetition_detector.last_reset[session_id]

def start_scheduler():
    scheduler.add_job(async_wrapper(check_for_nudge), 'interval', seconds=25, max_instances=2)
    scheduler.add_job(async_wrapper(recommend_game), 'interval', seconds=2, max_instances=2)
    scheduler.add_job(async_wrapper(get_followup), 'interval', seconds=3, max_instances=2)
    scheduler.add_job(async_wrapper(ask_for_name_if_needed), 'interval', seconds=4, max_instances=2)
    scheduler.add_job(async_wrapper(cleanup_repetition_detector), 'interval', hours=1, max_instances=1)
    scheduler.start()

def stop_scheduler():
    scheduler.shutdown()
