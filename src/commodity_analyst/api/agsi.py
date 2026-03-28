import pandas as pd
import streamlit as st

from commodity_analyst.api.gie_client import GIEClient
from commodity_analyst.config import GIE_API_KEY

_BASE_URL = "https://agsi.gie.eu/api"

_COLUMN_MAP: dict[str, str] = {
    "gasDayStart": "gas_day",
    "full": "full_pct",
    "gasInStorage": "gas_in_storage",
    "injection": "injection",
    "withdrawal": "withdrawal",
    "workingGasVolume": "working_gas_volume",
    "status": "status",
}


def _to_dataframe(records: list[dict[str, object]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=pd.Index(_COLUMN_MAP.values())).set_index("gas_day")
    df = pd.DataFrame(records)
    cols = [c for c in _COLUMN_MAP if c in df.columns]
    df = df[cols]
    df.columns = pd.Index([_COLUMN_MAP.get(str(c), str(c)) for c in df.columns])
    df["gas_day"] = pd.to_datetime(df["gas_day"])
    df = df.set_index("gas_day").sort_index()
    for col in df.columns:
        if col != "status":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def get_eu_storage(from_date: str, to_date: str) -> pd.DataFrame:
    """Fetch EU-aggregate daily storage data. Returns DataFrame indexed by gas_day."""
    with GIEClient(_BASE_URL, GIE_API_KEY) as client:
        records = client.get_all("", {"type": "eu", "from": from_date, "to": to_date})
    return _to_dataframe(records)


@st.cache_data(ttl=3600)
def get_country_storage(country: str, from_date: str, to_date: str) -> pd.DataFrame:
    """Fetch single-country daily storage data. `country` is a 2-letter code (e.g. 'DE')."""
    with GIEClient(_BASE_URL, GIE_API_KEY) as client:
        records = client.get_all("", {"country": country, "from": from_date, "to": to_date})
    return _to_dataframe(records)
