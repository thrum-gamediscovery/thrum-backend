import os
from celery import Celery
from app.core.config import settings


celery_app = Celery(
    "thrum_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.followup"]
)

celery_app.conf.beat_schedule = {
    "send-followup-every-15-mins": {
        "task": "app.tasks.followup.send_feedback_followups",
        "schedule": 900.0,  # 15 minutes in seconds
    },
    "check-delayed-followups": {
        "task": "app.tasks.followup.check_delayed_followups",
        "schedule": 300.0,  # Run every 5 minutes
    },
}
celery_app.conf.timezone = 'UTC'
