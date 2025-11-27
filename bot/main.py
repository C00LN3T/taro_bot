import asyncio
import logging
import sys
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

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


async def start_polling(dp: Dispatcher, bot: Bot) -> None:
    await dp.start_polling(bot)


async def start_webhook(config: BotConfig, dp: Dispatcher, bot: Bot) -> None:
    webhook_url = config.webhook_url
    if not webhook_url:
        raise ValueError("WEBHOOK_HOST/WEBHOOK_PATH must be configured when USE_WEBHOOK=true")

    app = web.Application()
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=config.webhook_secret,
    )
    webhook_handler.register(app, path=config.webhook_path)
    setup_application(app, dp, bot=bot)

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(url=webhook_url, secret_token=config.webhook_secret)

    logging.info("Starting webhook on port %s at path %s", config.webhook_port, config.webhook_path)
    await web._run_app(app, host="0.0.0.0", port=config.webhook_port)


async def main() -> None:
    config = BotConfig.load()
    init_db(config)
    bot = Bot(token=config.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = create_dispatcher(config)

    if config.use_webhook:
        await start_webhook(config, dp, bot)
    else:
        await start_polling(dp, bot)


if __name__ == "__main__":
    asyncio.run(main())
