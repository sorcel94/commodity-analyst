from __future__ import annotations

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Commodity Analyst", layout="wide", page_icon=":chart_with_upwards_trend:")

from commodity_analyst.api.agsi import get_eu_storage
from commodity_analyst.api.alsi import get_eu_lng
from commodity_analyst.api.market import get_ttf

st.title("Commodity Analyst")
st.caption("EU natural gas market dashboard  - storage, LNG, and price signals")

with st.expander("What is this dashboard?"):
    st.markdown("""
This dashboard tracks whether EU natural gas storage is on pace to meet the
**90% fill target by November 1**  - a key regulatory milestone. If storage
falls behind, prices tend to rise as the market prices in winter scarcity risk.

**What you'll find here:**
- **Storage Overview**  - current fill vs the 5-year average and the EU target trajectory
- **Injection Analysis**  - is gas being pumped into storage fast enough?
- **LNG Terminals**  - are LNG imports supporting supply or running at capacity?
- **Market Benchmarks**  - TTF, Henry Hub, and JKM price trends and correlations
- **Imbalance Signals**  - a composite scorecard summarizing all of the above

Green = supply looks comfortable. Red = thesis for rising winter prices is supported.
""")

# Fetch latest data points
today = st.session_state.get("_today")
if today is None:
    import datetime

    today = datetime.date.today().isoformat()

try:
    storage = get_eu_storage(today, today)
    if storage.empty:
        # Try yesterday if today's data isn't published yet
        import datetime

        yesterday = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
        storage = get_eu_storage(yesterday, today)
except Exception:
    storage = None

try:
    lng = get_eu_lng(today, today)
    if lng.empty:
        import datetime

        yesterday = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
        lng = get_eu_lng(yesterday, today)
except Exception:
    lng = None

try:
    ttf = get_ttf("5d")
except Exception:
    ttf = None

# KPI cards
c1, c2, c3, c4 = st.columns(4)

with c1:
    if storage is not None and not storage.empty:
        fill = storage["full_pct"].iloc[-1]
        st.metric("EU Storage Fill", f"{fill:.1f}%")
        if fill >= 80:
            st.caption("Comfortable  - well on track for winter.")
        elif fill >= 60:
            st.caption("Moderate  - needs sustained injection to reach 90%.")
        elif fill >= 40:
            st.caption("Low  - significant injection needed before November.")
        else:
            st.caption("Very low  - well behind the typical seasonal trajectory.")
    else:
        st.metric("EU Storage Fill", "N/A")

with c2:
    if ttf is not None and not ttf.empty:
        price = ttf["close"].iloc[-1]
        change = ttf["change"].iloc[-1]
        st.metric("TTF Front-Month", f"\u20ac{price:.2f}/MWh", f"{change:+.2f}")
        if price > 50:
            st.caption("Elevated  - market pricing in supply tightness.")
        elif price > 30:
            st.caption("Moderate  - within recent historical range.")
        else:
            st.caption("Low  - market sees comfortable supply outlook.")
    else:
        st.metric("TTF Front-Month", "N/A")

with c3:
    if lng is not None and not lng.empty:
        inv = lng["lng_inventory"].iloc[-1]
        st.metric("EU LNG Inventory", f"{inv:,.0f} GWh")
        st.caption("LNG stored at EU import terminals, available for regasification.")
    else:
        st.metric("EU LNG Inventory", "N/A")

with c4:
    if storage is not None and not storage.empty:
        latest_date = pd.Timestamp(storage.index[-1])  # pyright: ignore[reportArgumentType]
        status = storage["status"].iloc[-1]
        _STATUS_LABELS = {"E": "Estimated", "C": "Confirmed", "N": "No data"}
        status_label = _STATUS_LABELS.get(str(status), str(status))
        st.metric("Latest Data", str(latest_date.date()), f"Status: {status_label}")
    else:
        st.metric("Latest Data", "N/A")

st.divider()
st.markdown("""
**Navigate using the sidebar** to explore:
- **Storage Overview**  - fill levels vs 5-year average and EU target
- **Injection Analysis**  - injection pace and country breakdown
- **LNG Terminals**  - terminal rankings, send-out, and drill-down
- **Market Benchmarks**  - TTF, Henry Hub, JKM prices and correlations
- **Imbalance Signals**  - thesis validation signals (green/yellow/red)
""")
