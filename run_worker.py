import asyncio
from app.tasks.scheduler import start_scheduler, stop_scheduler
import signal

async def main():
    await start_scheduler()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(sig, stop.set)
        except NotImplementedError: pass
    await stop.wait()
    await stop_scheduler()

if __name__ == "__main__":
    asyncio.run(main())
