"""Local/dev entrypoint: long polling. Production should prefer webhook mode (see app/api/main.py)."""
import asyncio
import logging

from app.bot.bot import get_bot, get_dispatcher


async def main():
    logging.basicConfig(level=logging.INFO)
    bot = get_bot()
    dp = get_dispatcher()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
