import os
from dotenv import load_dotenv

load_dotenv()


def get_required(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


class BackendConfig:
    def __init__(self):
        self.secret_key: str = get_required("FLASK_SECRET_KEY")
        self.host: str = os.getenv("FLASK_HOST", "0.0.0.0")
        self.port: int = int(os.getenv("FLASK_PORT", "5000"))
        self.api_key: str = get_required("API_KEY")
        cors_origins = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:8081,http://localhost:19006",
        )
        self.cors_origins: list[str] = [o.strip() for o in cors_origins.split(",") if o.strip()]
        self.match_timeout: int = int(os.getenv("MATCH_TIMEOUT_SECONDS", "180"))

        # Discord notifications (optional)
        self.discord_bot_token: str | None = os.getenv("DISCORD_BOT_TOKEN") or None
        self.discord_user_id: int | None = None
        discord_user_id_raw = os.getenv("DISCORD_USER_ID")
        if discord_user_id_raw:
            try:
                self.discord_user_id = int(discord_user_id_raw)
            except ValueError:
                pass
