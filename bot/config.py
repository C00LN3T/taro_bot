from dataclasses import dataclass
import os


@dataclass
class BotConfig:
    token: str
    admin_ids: tuple[int, ...] = ()
    default_language: str = "ru"
    database_url: str = "sqlite:///./gadalka.db"
    daily_free_limit: int = 5

    @staticmethod
    def load() -> "BotConfig":
        token = os.environ.get("BOT_TOKEN")
        if not token:
            raise ValueError("BOT_TOKEN is not set in environment")
        admin_ids_env = os.environ.get("ADMIN_IDS", "")
        admin_ids = tuple(int(value) for value in admin_ids_env.split(",") if value.strip())
        default_language = os.environ.get("DEFAULT_LANGUAGE", "ru")
        database_url = os.environ.get("DATABASE_URL", "sqlite:///./gadalka.db")
        daily_free_limit = int(os.environ.get("DAILY_FREE_LIMIT", "5"))
        return BotConfig(
            token=token,
            admin_ids=admin_ids,
            default_language=default_language,
            database_url=database_url,
            daily_free_limit=daily_free_limit,
        )
