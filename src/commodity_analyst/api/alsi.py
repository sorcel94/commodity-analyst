from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from commodity_analyst.api.gie_client import GIEClient
from commodity_analyst.config import GIE_API_KEY

_BASE_URL = "https://alsi.gie.eu/api"


def _flatten_record(record: dict[str, Any]) -> dict[str, Any]:
    """Extract nested inventory/dtmi GWh values into flat fields."""
    flat: dict[str, Any] = {}
    for key, value in record.items():
        if key == "inventory" and isinstance(value, dict):
            flat["lngInventory"] = value.get("gwh")
        elif key == "dtmi" and isinstance(value, dict):
            flat["dtmi"] = value.get("gwh")
        else:
            flat[key] = value
    return flat


_TIMESERIES_COLUMNS: dict[str, str] = {
    "gasDayStart": "gas_day",
    "lngInventory": "lng_inventory",
    "sendOut": "send_out",
    "dtmi": "dtmi",
    "dtrs": "dtrs",
    "status": "status",
}


def _to_timeseries(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=pd.Index(_TIMESERIES_COLUMNS.values())).set_index("gas_day")
    flat = [_flatten_record(r) for r in records]
    df = pd.DataFrame(flat)
    cols = [c for c in _TIMESERIES_COLUMNS if c in df.columns]
    df = df[cols]
    df.columns = pd.Index([_TIMESERIES_COLUMNS.get(str(c), str(c)) for c in df.columns])
    df["gas_day"] = pd.to_datetime(df["gas_day"])
    df = df.set_index("gas_day").sort_index()
    for col in df.columns:
        if col != "status":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=3600)
def get_eu_lng(from_date: str, to_date: str) -> pd.DataFrame:
    """Fetch EU-aggregate daily LNG data. Returns DataFrame indexed by gas_day."""
    with GIEClient(_BASE_URL, GIE_API_KEY) as client:
        records = client.get_all("", {"type": "eu", "from": from_date, "to": to_date})
    return _to_timeseries(records)


@st.cache_data(ttl=3600)
def get_terminal_listing() -> pd.DataFrame:
    """Fetch all LNG terminals. Returns DataFrame with name, country, eic, company, type."""
    with GIEClient(_BASE_URL, GIE_API_KEY) as client:
        body: list[dict[str, Any]] = client.get_json("about", {"show": "listing"})

    rows: list[dict[str, Any]] = []
    for company_entry in body:
        company_name = company_entry.get("name", "")
        company_eic = company_entry.get("eic", "")
        for facility in company_entry.get("facilities", []):
            rows.append(
                {
                    "name": facility.get("name"),
                    "country": facility.get("country"),
                    "eic": facility.get("eic"),
                    "company_eic": company_eic,
                    "company_name": company_name,
                    "type": facility.get("type"),
                }
            )
    return pd.DataFrame(rows)


@st.cache_data(ttl=3600)
def get_terminal_data(country: str, company: str, facility: str, from_date: str, to_date: str) -> pd.DataFrame:
    """Fetch time series for a single terminal. Requires country code, company EIC, and facility EIC."""
    with GIEClient(_BASE_URL, GIE_API_KEY) as client:
        records = client.get_all(
            "",
            {
                "country": country,
                "company": company,
                "facility": facility,
                "from": from_date,
                "to": to_date,
            },
        )
    return _to_timeseries(records)


@st.cache_data(ttl=3600)
def get_unavailability() -> pd.DataFrame:
    """Fetch current planned/unplanned outages at LNG terminals."""
    with GIEClient(_BASE_URL, GIE_API_KEY) as client:
        records = client.get_all("unavailability", {})

    rows: list[dict[str, Any]] = []
    for r in records:
        facility = r.get("facility", {})
        company = r.get("company", {})
        country = r.get("country", {})
        rows.append(
            {
                "facility_name": facility.get("name") if isinstance(facility, dict) else None,
                "facility_eic": facility.get("eic") if isinstance(facility, dict) else None,
                "company_name": company.get("name") if isinstance(company, dict) else None,
                "country_name": country.get("name") if isinstance(country, dict) else None,
                "country_code": country.get("code") if isinstance(country, dict) else None,
                "start": r.get("start"),
                "end": r.get("end"),
                "capacity": r.get("capacity"),
                "type": r.get("type"),
                "description": r.get("description"),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df["start"] = pd.to_datetime(df["start"])
        df["end"] = pd.to_datetime(df["end"])
        df["capacity"] = pd.to_numeric(df["capacity"], errors="coerce")
    return df
