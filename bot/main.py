import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from .config import BotConfig
from .db import init_db
from .handlers import router

logging.basicConfig(level=logging.INFO)


def create_dispatcher(config: BotConfig) -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    dp["config"] = config
    return dp


async def main() -> None:
    config = BotConfig.load()
    init_db(config)
    bot = Bot(token=config.token, parse_mode=ParseMode.HTML)
    dp = create_dispatcher(config)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
