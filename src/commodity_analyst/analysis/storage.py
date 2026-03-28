from __future__ import annotations

import numpy as np
import pandas as pd


def five_year_average(df_multi_year: pd.DataFrame) -> pd.DataFrame:
    """Compute day-of-year average fill % from multi-year storage data.

    Input: DataFrame with DatetimeIndex and `full_pct` column (multiple years).
    Returns: DataFrame indexed by day_of_year (1-366) with columns `avg_full_pct`, `std_full_pct`.
    """
    s = df_multi_year["full_pct"].copy()
    s.index = pd.DatetimeIndex(df_multi_year.index).day_of_year  # pyright: ignore[reportAttributeAccessIssue]
    grouped = s.groupby(s.index)
    return pd.DataFrame({
        "avg_full_pct": grouped.mean(),
        "std_full_pct": grouped.std(),
    })


def target_curve(year: int) -> pd.DataFrame:
    """Generate the EU 90% storage fill target curve for a given year.

    Linear interpolation between regulatory milestones.
    Returns: DataFrame indexed by date with column `target_pct`.
    """
    milestones = {
        f"{year}-02-01": 45.0,
        f"{year}-04-01": 35.0,
        f"{year}-05-01": 40.0,
        f"{year}-07-01": 60.0,
        f"{year}-09-01": 80.0,
        f"{year}-11-01": 90.0,
        f"{year}-12-01": 85.0,
    }
    dates = pd.to_datetime(list(milestones.keys()))
    values = list(milestones.values())
    full_range = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    interp = np.interp(
        full_range.to_julian_date(),
        dates.to_julian_date(),
        values,
        left=values[0],
        right=values[-1],
    )
    df = pd.DataFrame({"target_pct": interp}, index=full_range)
    df.index.name = "date"
    return df


def fill_deviation(current_df: pd.DataFrame, avg_df: pd.DataFrame) -> pd.Series:  # type: ignore[type-arg]
    """Current fill % minus 5-year average on matching day-of-year.

    current_df: DatetimeIndex with `full_pct` column (single year).
    avg_df: day_of_year index with `avg_full_pct` column (from five_year_average).
    Returns: Series indexed like current_df.
    """
    doy = pd.DatetimeIndex(current_df.index).day_of_year  # pyright: ignore[reportAttributeAccessIssue]
    avg_aligned = avg_df["avg_full_pct"].reindex(doy).values
    deviation = current_df["full_pct"].values - avg_aligned  # pyright: ignore[reportOperatorIssue]
    return pd.Series(deviation, index=current_df.index, name="deviation")


def days_ahead_behind(current_df: pd.DataFrame, avg_df: pd.DataFrame) -> int:
    """How many days current fill is ahead (+) or behind (-) the 5-year average.

    Finds the day_of_year in the average curve closest to today's fill level,
    then returns the difference in days.
    """
    latest_fill: float = float(current_df["full_pct"].iloc[-1])
    latest_doy: int = int(pd.DatetimeIndex(current_df.index)[-1].day_of_year)  # pyright: ignore[reportAttributeAccessIssue]

    avg_series = avg_df["avg_full_pct"].dropna()
    closest_doy = int(avg_series.sub(latest_fill).abs().idxmin())  # pyright: ignore[reportArgumentType]
    return latest_doy - closest_doy


def storage_z_score(current_fill: float, avg_fill: float, std_fill: float) -> float:
    """Z-score of current fill vs historical average for the same day-of-year."""
    if std_fill == 0:
        return 0.0
    return (current_fill - avg_fill) / std_fill
