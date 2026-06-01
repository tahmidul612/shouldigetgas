"""
Scheduler — orchestrates Part 1 (price collection) and Part 2 (analytics).

Two independent jobs:
  - Price collector: every PRICE_REFRESH_MINUTES (default 30)
  - Analytics engine: every ANALYTICS_REFRESH_HOURS (default 6)

Run:
    cd shouldigetgas
    python backend/scheduler.py

Or use shell wrappers in scripts/ for cron-based deployment.
"""
import sys
import logging
import signal
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
import db
from config import PRICE_REFRESH_MINUTES, ANALYTICS_REFRESH_HOURS

log = logging.getLogger(__name__)


def job_collect_prices():
    """30-minute job: pull current gas prices for all regions."""
    try:
        from price_collector import run as collect
        collect()
    except Exception as e:
        log.error("Price collection job failed: %s", e, exc_info=True)


def job_run_analytics():
    """6-hour job: run analytics pipeline and write data.json."""
    try:
        from snapshot import run as analyze
        analyze()
    except Exception as e:
        log.error("Analytics job failed: %s", e, exc_info=True)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    )

    db.init_db()
    log.info("Database ready.")

    # Run both jobs immediately on startup so data.json is populated
    log.info("Running initial price collection…")
    job_collect_prices()
    log.info("Running initial analytics…")
    job_run_analytics()

    scheduler = BlockingScheduler(timezone="UTC")

    scheduler.add_job(
        job_collect_prices,
        trigger=IntervalTrigger(minutes=PRICE_REFRESH_MINUTES),
        id="price_collector",
        name=f"Price Collector (every {PRICE_REFRESH_MINUTES}min)",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        job_run_analytics,
        trigger=IntervalTrigger(hours=ANALYTICS_REFRESH_HOURS),
        id="analytics_engine",
        name=f"Analytics Engine (every {ANALYTICS_REFRESH_HOURS}h)",
        max_instances=1,
        coalesce=True,
    )

    def _shutdown(signum, frame):
        log.info("Signal %s received — shutting down scheduler…", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT,  _shutdown)

    log.info(
        "Scheduler running: prices every %dmin, analytics every %dh",
        PRICE_REFRESH_MINUTES, ANALYTICS_REFRESH_HOURS,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
