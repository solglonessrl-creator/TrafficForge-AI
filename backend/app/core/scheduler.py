from __future__ import annotations

from typing import Awaitable, Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


_scheduler: Optional[AsyncIOScheduler] = None


def start_scheduler(daily_job: Callable[[], Awaitable[None]]) -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        daily_job,
        CronTrigger(hour=9, minute=0),
        id="trafficforge_daily_pipeline",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60 * 60,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None

