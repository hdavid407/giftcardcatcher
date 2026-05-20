import os
from dotenv import load_dotenv

load_dotenv()


def get_required(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


class ScraperConfig:
    def __init__(self):
        self.api_id: int = int(get_required("TELEGRAM_API_ID"))
        self.api_hash: str = get_required("TELEGRAM_API_HASH")
        self.phone: str = get_required("TELEGRAM_PHONE")
        self.target_bot: str = get_required("TARGET_BOT_USERNAME")
        self.refresh_button_text: str = os.getenv("REFRESH_BUTTON_TEXT", "Refresh")
        self.purchase_button_text: str = os.getenv("PURCHASE_BUTTON_TEXT", "Purchase")
        self.poll_interval: int = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))
        self.match_timeout: int = int(os.getenv("MATCH_TIMEOUT_SECONDS", "180"))
        self.backend_url: str = os.getenv("BACKEND_URL", "http://localhost:5000")
        self.api_key: str = os.getenv("API_KEY", "")
