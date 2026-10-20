import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session

from app.db.session import engine
from app.services.delayed_orders import check_delayed_orders

logger = logging.getLogger(__name__)


async def _run_delayed_order_check() -> None:
    with Session(engine) as db_session:
        await check_delayed_orders(db_session)


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_delayed_order_check,
        trigger=CronTrigger(hour=8, minute=0),
        id="delayed-order-email-alerts",
        replace_existing=True,
    )
    return scheduler
