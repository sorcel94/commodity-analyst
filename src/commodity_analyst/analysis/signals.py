from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from commodity_analyst.analysis.injection import injection_deficit, rolling_net_injection
from commodity_analyst.analysis.storage import storage_z_score

_NOV_1_TARGET = 90.0


def _signal(value: float, status: str, label: str) -> dict[str, Any]:
    return {"value": value, "status": status, "label": label}


def _z_score_signal(storage_df: pd.DataFrame, avg_df: pd.DataFrame) -> dict[str, Any]:
    latest_fill = float(storage_df["full_pct"].iloc[-1])
    doy = int(pd.DatetimeIndex(storage_df.index)[-1].day_of_year)  # pyright: ignore[reportAttributeAccessIssue]
    avg_val = avg_df["avg_full_pct"].get(doy)
    avg = float(avg_val) if avg_val is not None else latest_fill
    std_val = avg_df["std_full_pct"].get(doy)
    std = float(std_val) if std_val is not None else 1.0
    z = storage_z_score(latest_fill, avg, std)
    if z < -1.5:
        status = "red"
    elif z < -0.5:
        status = "yellow"
    else:
        status = "green"
    return _signal(round(z, 2), status, "Storage Z-Score")


def _injection_deficit_signal(storage_df: pd.DataFrame) -> dict[str, Any]:
    latest_fill = float(storage_df["full_pct"].iloc[-1])
    wgv = float(storage_df["working_gas_volume"].iloc[-1])
    net_inj = rolling_net_injection(storage_df, window=7)
    current_net = float(net_inj.iloc[-1])
    latest_date = pd.Timestamp(storage_df.index[-1])  # pyright: ignore[reportArgumentType]
    nov_1 = pd.Timestamp(f"{latest_date.year}-11-01")
    days_left = int(max((nov_1 - latest_date).days, 0))
    deficit = injection_deficit(latest_fill, _NOV_1_TARGET, wgv, days_left, current_net)
    if deficit > 500:
        status = "red"
    elif deficit > 0:
        status = "yellow"
    else:
        status = "green"
    return _signal(round(deficit, 1), status, "Injection Deficit (GWh/d)")


def _days_of_supply_signal(storage_df: pd.DataFrame) -> dict[str, Any]:
    """Current storage / average winter withdrawal rate."""
    gas_in_storage_twh = float(storage_df["gas_in_storage"].iloc[-1])
    gas_in_storage_gwh = gas_in_storage_twh * 1000.0
    # Use average withdrawal from the last 30 days of data as proxy
    recent_withdrawal = storage_df["withdrawal"].tail(30).mean()
    if recent_withdrawal > 0:
        days = gas_in_storage_gwh / float(recent_withdrawal)
    else:
        days = float("inf")
    if days < 30:
        status = "red"
    elif days < 60:
        status = "yellow"
    else:
        status = "green"
    return _signal(round(days, 0), status, "Days of Supply")


def _yoy_fill_signal(storage_df: pd.DataFrame, storage_prev_year_df: pd.DataFrame) -> dict[str, Any]:
    current_fill = float(storage_df["full_pct"].iloc[-1])
    # Find matching day-of-year in previous year
    current_doy = int(pd.DatetimeIndex(storage_df.index)[-1].day_of_year)  # pyright: ignore[reportAttributeAccessIssue]
    prev_doys = pd.DatetimeIndex(storage_prev_year_df.index).day_of_year  # pyright: ignore[reportAttributeAccessIssue]
    mask = prev_doys == current_doy
    if mask.any():
        prev_fill = float(storage_prev_year_df.loc[mask, "full_pct"].iloc[0])
    else:
        prev_fill = current_fill
    delta = current_fill - prev_fill
    if delta < -5:
        status = "red"
    elif delta < 0:
        status = "yellow"
    else:
        status = "green"
    return _signal(round(delta, 2), status, "YoY Fill Change (pp)")


def _terminal_utilization_signal(lng_df: pd.DataFrame) -> dict[str, Any]:
    inventory = float(lng_df["lng_inventory"].iloc[-1])
    dtmi = float(lng_df["dtmi"].iloc[-1])
    utilization = (inventory / dtmi * 100.0) if dtmi > 0 else 0.0
    if utilization > 85:
        status = "red"
    elif utilization > 70:
        status = "yellow"
    else:
        status = "green"
    return _signal(round(utilization, 1), status, "Terminal Utilization (%)")


def _outage_signal(unavail_df: pd.DataFrame) -> dict[str, Any]:
    if unavail_df.empty:
        return _signal(0, "green", "Active Outages")
    today = pd.Timestamp(date.today())
    active = unavail_df[(unavail_df["start"] <= today) & (unavail_df["end"] >= today)]
    count = len(active)
    if count > 10:
        status = "red"
    elif count > 3:
        status = "yellow"
    else:
        status = "green"
    return _signal(count, status, "Active Outages")


def compute_signals(
    storage_df: pd.DataFrame,
    storage_prev_year_df: pd.DataFrame,
    avg_df: pd.DataFrame,
    lng_df: pd.DataFrame,
    unavail_df: pd.DataFrame,
) -> dict[str, dict[str, Any]]:
    """Compute all imbalance signals.

    Args:
        storage_df: Current year EU storage data.
        storage_prev_year_df: Previous year EU storage data (for YoY).
        avg_df: 5-year average from five_year_average().
        lng_df: EU LNG data from get_eu_lng().
        unavail_df: Unavailability data from get_unavailability().

    Returns: Dict of signal_name -> {value, status, label}.
    """
    return {
        "z_score": _z_score_signal(storage_df, avg_df),
        "injection_deficit": _injection_deficit_signal(storage_df),
        "days_of_supply": _days_of_supply_signal(storage_df),
        "yoy_fill": _yoy_fill_signal(storage_df, storage_prev_year_df),
        "terminal_utilization": _terminal_utilization_signal(lng_df),
        "outage_count": _outage_signal(unavail_df),
    }
