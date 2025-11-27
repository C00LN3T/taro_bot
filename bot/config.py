from dataclasses import dataclass
import os


@dataclass
class BotConfig:
    token: str
    admin_ids: tuple[int, ...] = ()
    default_language: str = "ru"
    database_url: str = "sqlite:///./gadalka.db"
    daily_free_limit: int = 5
    use_webhook: bool = False
    webhook_host: str | None = None
    webhook_path: str = "/webhook"
    webhook_secret: str | None = None
    webhook_port: int = 8080

    @property
    def webhook_url(self) -> str | None:
        if not self.webhook_host:
            return None
        return f"{self.webhook_host.rstrip('/')}{self.webhook_path}"

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

        use_webhook = os.environ.get("USE_WEBHOOK", "false").lower() == "true"
        webhook_host = os.environ.get("WEBHOOK_HOST") or os.environ.get("RENDER_EXTERNAL_URL")
        webhook_path = os.environ.get("WEBHOOK_PATH", "/webhook")
        webhook_secret = os.environ.get("WEBHOOK_SECRET")
        webhook_port = int(os.environ.get("PORT", os.environ.get("WEBHOOK_PORT", "8080")))

        return BotConfig(
            token=token,
            admin_ids=admin_ids,
            default_language=default_language,
            database_url=database_url,
            daily_free_limit=daily_free_limit,
            use_webhook=use_webhook,
            webhook_host=webhook_host,
            webhook_path=webhook_path,
            webhook_secret=webhook_secret,
            webhook_port=webhook_port,
        )
