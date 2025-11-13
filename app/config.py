import os
from dataclasses import dataclass


@dataclass
class Config:
    bot_token: str
    database_url: str
    alert_threshold_percent: float = 5.0
    poll_interval_seconds: int = 60
    whale_poll_interval_seconds: int = 60

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("BOT_TOKEN")
        db_url = os.getenv("DATABASE_URL")
        if not token:
            raise RuntimeError("BOT_TOKEN is not set")
        if not db_url:
            raise RuntimeError("DATABASE_URL is not set")

        alert = float(os.getenv("ALERT_THRESHOLD_PERCENT", "5.0"))
        poll = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
        whale_poll = int(os.getenv("WHALE_POLL_INTERVAL_SECONDS", "60"))
        return cls(
            bot_token=token,
            database_url=db_url,
            alert_threshold_percent=alert,
            poll_interval_seconds=poll,
            whale_poll_interval_seconds=whale_poll,
        )
