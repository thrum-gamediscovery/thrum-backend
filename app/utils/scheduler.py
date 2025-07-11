import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.nudge_checker import check_for_nudge
from app.services.thrum_router.phase_delivery import recommend_game
from app.services.thrum_router.phase_followup import get_followup
from app.services.thrum_router.phase_confirmation import ask_for_name_if_needed

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

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(async_wrapper(check_for_nudge), 'interval', seconds=10)
    scheduler.add_job(async_wrapper(recommend_game), 'interval', seconds=10)
    print("--------------------------------------get followup called")
    scheduler.add_job(async_wrapper(get_followup), 'interval', seconds=10)
    scheduler.add_job(async_wrapper(ask_for_name_if_needed), 'interval', seconds=10)
    scheduler.start()
