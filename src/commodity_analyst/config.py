import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _require_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


GIE_API_KEY: str = _require_env("GIE_API_KEY")
FRED_API_KEY: str = _require_env("FRED_API_KEY")
