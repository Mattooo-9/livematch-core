"""
Production bot entrypoint with:
- Distributed leader election (Active-Passive cluster)
- Watchdog (memory monitoring + auto-restart)
- Graceful shutdown
"""
import asyncio, logging, signal, sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
log = logging.getLogger("livematch.bot")


async def run():
    from app.bot.bot import get_bot, get_dispatcher
    from app.core.distributed_lock import start_leader_election, stop_leader_election, NODE_ID_VALUE
    from app.core.watchdog import start_watchdog, stop_watchdog

    bot = get_bot()
    dp  = get_dispatcher()

    log.info(f"Bot node {NODE_ID_VALUE} starting...")

    is_active = await start_leader_election()
    if not is_active:
        log.info("This node is PASSIVE — monitoring lock, ready to take over...")
        # Passive mode: keep process alive, monitor lock, take over if leader dies
        while True:
            await asyncio.sleep(5)
            is_active = await start_leader_election()
            if is_active:
                log.info("Became ACTIVE leader — starting polling")
                break

    restart_event = asyncio.Event()

    async def restart_bot():
        restart_event.set()

    watchdog_task = await start_watchdog(restart_bot)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    await bot.delete_webhook(drop_pending_updates=True)

    log.info("Starting polling (ACTIVE mode)...")
    polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))

    done, pending = await asyncio.wait(
        [polling_task, asyncio.create_task(stop_event.wait()),
         asyncio.create_task(restart_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    for t in pending:
        t.cancel()

    await stop_watchdog()
    await stop_leader_election()

    if restart_event.is_set():
        log.warning("Restarting process...")
        await bot.session.close()
        python = sys.executable
        import os; os.execv(python, [python] + sys.argv)

    await bot.session.close()
    log.info("Bot stopped gracefully.")


if __name__ == "__main__":
    asyncio.run(run())
