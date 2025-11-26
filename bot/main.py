import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.config import BotConfig
from bot.db import init_db
from bot.handlers import router

logging.basicConfig(level=logging.INFO)


def create_dispatcher(config: BotConfig) -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    dp["config"] = config
    return dp


async def main() -> None:
    config = BotConfig.load()
    init_db(config)
    bot = Bot(token=config.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = create_dispatcher(config)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
