import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _get_secret(key: str) -> str:
    # Streamlit Cloud secrets first
    try:
        import streamlit as st

        value = st.secrets[key]
        if isinstance(value, str) and value:
            return value
    except (KeyError, FileNotFoundError, ImportError):
        pass

    # Fall back to environment variable
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Missing required secret: {key} (set in .streamlit/secrets.toml or .env)")
    return value


GIE_API_KEY: str = _get_secret("GIE_API_KEY")
FRED_API_KEY: str = _get_secret("FRED_API_KEY")
