import asyncio

from app.core.scheduler import create_scheduler


async def run_worker() -> None:
    scheduler = create_scheduler()
    scheduler.start()
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
