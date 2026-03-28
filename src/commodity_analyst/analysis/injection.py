from __future__ import annotations

import pandas as pd


def rolling_net_injection(df: pd.DataFrame, window: int = 7) -> pd.Series:  # type: ignore[type-arg]
    """Rolling average of net injection (injection - withdrawal) in GWh/d.

    Input: DataFrame with `injection` and `withdrawal` columns (DatetimeIndex).
    Returns: Series with rolling mean, same index.
    """
    net = df["injection"] - df["withdrawal"]
    return net.rolling(window=window, min_periods=1).mean()


def injection_deficit(
    current_fill_pct: float,
    target_fill_pct: float,
    working_gas_volume_twh: float,
    days_remaining: int,
    current_net_injection_gwh_d: float,
) -> float:
    """GWh/d injection deficit: required rate minus current rate.

    Positive = deficit (need more injection), negative = surplus.
    """
    gap_twh = (target_fill_pct - current_fill_pct) / 100.0 * working_gas_volume_twh
    gap_gwh = gap_twh * 1000.0
    if days_remaining <= 0:
        return 0.0
    required_gwh_d = gap_gwh / days_remaining
    return required_gwh_d - current_net_injection_gwh_d
