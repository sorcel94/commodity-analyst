import datetime

import pandas as pd
import streamlit as st

from commodity_analyst.analysis.signals import compute_signals
from commodity_analyst.analysis.storage import five_year_average
from commodity_analyst.api.agsi import get_eu_storage
from commodity_analyst.api.alsi import get_eu_lng, get_unavailability
from commodity_analyst.api.market import get_ttf

st.set_page_config(page_title="Commodity Analyst", layout="wide", page_icon=":chart_with_upwards_trend:")

# Fetch data
current_year = datetime.date.today().year
today_str = datetime.date.today().isoformat()

with st.spinner("Loading..."):
    try:
        storage = get_eu_storage(f"{current_year}-01-01", today_str)
        if storage.empty:
            storage = None
    except Exception:
        storage = None

    try:
        storage_prev = get_eu_storage(f"{current_year - 1}-01-01", f"{current_year - 1}-12-31")
    except Exception:
        storage_prev = pd.DataFrame()

    try:
        multi_year = get_eu_storage(f"{current_year - 5}-01-01", f"{current_year - 1}-12-31")
        avg = five_year_average(multi_year)
    except Exception:
        avg = pd.DataFrame()

    try:
        lng = get_eu_lng(f"{current_year}-03-01", today_str)
        if lng.empty:
            lng = None
    except Exception:
        lng = None

    try:
        unavail = get_unavailability()
    except Exception:
        unavail = pd.DataFrame()

    try:
        ttf = get_ttf("5d")
    except Exception:
        ttf = None

# Compute signals
signals = None
if storage is not None and not storage.empty and lng is not None and not lng.empty:
    try:
        signals = compute_signals(storage, storage_prev, avg, lng, unavail)
    except Exception:
        signals = None

# Page
st.title("Commodity Analyst")

# Thesis
st.markdown(
    "**Thesis: EU natural gas prices will rise next winter.**\n\n"
    + "The EU requires 90% gas storage by November 1. "
    + "With Russian pipeline supply largely gone, Europe depends on LNG imports to refill. "
    + "If storage falls behind schedule, the market prices in scarcity and TTF rises."
)

st.divider()

# Analysis
st.subheader("Where we stand today")

if signals is not None and storage is not None and not storage.empty:
    fill = float(storage["full_pct"].iloc[-1])
    z = signals["z_score"]
    inj = signals["injection_deficit"]
    yoy = signals["yoy_fill"]

    # Storage position
    if z["value"] < -1.5:
        storage_read = f"Storage is at **{fill:.1f}%**, well below the 5-year average for this time of year."
    elif z["value"] < -0.5:
        storage_read = f"Storage is at **{fill:.1f}%**, slightly below the 5-year average."
    else:
        storage_read = f"Storage is at **{fill:.1f}%**, in line with or above the 5-year average."

    # YoY comparison
    if yoy["value"] < -5:
        yoy_read = f"That is **{abs(yoy['value']):.1f} percentage points lower** than the same date last year."
    elif yoy["value"] < 0:
        yoy_read = f"That is **{abs(yoy['value']):.1f}pp below** last year at this date."
    else:
        yoy_read = f"That is **{yoy['value']:.1f}pp above** last year at this date."

    # Injection pace
    if inj["value"] > 500:
        inj_read = (
            f"To reach 90% by November, Europe needs **{inj['value']:,.0f} GWh/day** "
            + "more injection than the current pace. That is a very large gap to close."
        )
    elif inj["value"] > 0:
        inj_read = (
            f"To reach 90% by November, Europe needs **{inj['value']:,.0f} GWh/day** "
            + "more than the current pace. Achievable, but requires sustained effort."
        )
    else:
        inj_read = "At the current injection rate, Europe is on track to hit the 90% target by November."

    st.markdown(f"{storage_read} {yoy_read}")
    st.markdown(inj_read)

    # TTF context
    price: float | None = None
    if ttf is not None and not ttf.empty:
        price = float(ttf["close"].iloc[-1])
        if price > 50:
            st.markdown(f"TTF is trading at **\u20ac{price:.2f}/MWh**, elevated and reflecting supply concerns.")
        elif price > 30:
            st.markdown(f"TTF is at **\u20ac{price:.2f}/MWh**, within the recent historical range.")
        else:
            st.markdown(f"TTF is at **\u20ac{price:.2f}/MWh**, relatively low, suggesting the market feels comfortable.")

    # KPI cards with benchmarks
    st.markdown("")
    k1, k2, k3, k4 = st.columns(4)

    # 5-year avg fill for today's day-of-year
    doy = int(pd.DatetimeIndex(storage.index)[-1].day_of_year)  # pyright: ignore[reportAttributeAccessIssue]
    avg_fill_today = avg["avg_full_pct"].get(doy) if not avg.empty else None

    with k1:
        st.metric("EU Storage Fill", f"{fill:.1f}%")
        if avg_fill_today is not None:
            st.caption(f"5-year avg for this date: {float(avg_fill_today):.1f}%")

    with k2:
        if price is not None and ttf is not None and not ttf.empty:
            change = float(ttf["change"].iloc[-1])
            st.metric("TTF Front-Month", f"\u20ac{price:.2f}/MWh", f"{change:+.2f}")
            st.caption("EU benchmark gas price. Above \u20ac50 signals tight supply.")
        else:
            st.metric("TTF Front-Month", "N/A")

    with k3:
        days = signals["days_of_supply"]["value"]
        st.metric("Days of Supply", f"{days:.0f} days")
        st.caption("How long current storage lasts at recent withdrawal rates.")

    with k4:
        if lng is not None and not lng.empty:
            util = signals["terminal_utilization"]["value"]
            st.metric("LNG Terminal Use", f"{util:.0f}%")
            st.caption("Share of terminal capacity in use. Above 85% means little room for more imports.")
        else:
            st.metric("LNG Terminal Use", "N/A")

    st.divider()

    # Verdict
    st.subheader("Verdict")

    red_count = sum(1 for s in signals.values() if s["status"] == "red")
    green_count = sum(1 for s in signals.values() if s["status"] == "green")

    if red_count >= 3:
        st.error(
            "**Bullish.** Storage is behind, injection is lagging, and the data supports the thesis " + "that prices will rise heading into winter."
        )
    elif green_count >= 4:
        st.success(
            "**Bearish.** Storage is healthy, injection is on pace, and LNG supply is flowing. " + "The case for rising prices is currently weak."
        )
    else:
        st.info("**Neutral.** Some factors support higher prices, others don't. " + "No strong signal in either direction yet.")

    st.caption("For the full breakdown of all 6 signals, see the **Imbalance Signals** page in the sidebar.")

else:
    st.warning("Could not load enough data to run the analysis.")

# Navigation
st.divider()
st.markdown("Use the **sidebar** to explore: Storage Overview, Injection Analysis, " + "LNG Terminals, Market Benchmarks, and Imbalance Signals.")
