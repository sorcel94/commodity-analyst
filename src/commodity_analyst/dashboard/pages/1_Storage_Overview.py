import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from commodity_analyst.analysis.storage import (
    days_ahead_behind,
    fill_deviation,
    five_year_average,
    storage_z_score,
    target_curve,
)
from commodity_analyst.api.agsi import get_eu_storage

st.header("Storage Overview")
st.caption("Are we on track to meet the EU 90% storage target by November 1?")

current_year = datetime.date.today().year
today = datetime.date.today().isoformat()

# Fetch data
current = get_eu_storage(f"{current_year}-01-01", today)
multi_year = get_eu_storage(f"{current_year - 5}-01-01", f"{current_year - 1}-12-31")
avg = five_year_average(multi_year)
tc = target_curve(current_year)

# --- KPI delta cards ---
if not current.empty:
    latest_fill = float(current["full_pct"].iloc[-1])
    dev = fill_deviation(current, avg)
    latest_dev = float(dev.iloc[-1])
    dab = days_ahead_behind(current, avg)

    # Target deviation
    latest_date = pd.Timestamp(current.index[-1])  # pyright: ignore[reportArgumentType]
    target_series = tc["target_pct"]
    if latest_date in target_series.index:
        target_dev: float | None = latest_fill - float(target_series[latest_date])  # pyright: ignore[reportArgumentType]
    else:
        target_dev = None

    # Z-score
    doy = int(pd.DatetimeIndex(current.index)[-1].day_of_year)  # pyright: ignore[reportAttributeAccessIssue]
    avg_raw = avg["avg_full_pct"].get(doy)
    avg_val = float(avg_raw) if avg_raw is not None else latest_fill
    std_raw = avg["std_full_pct"].get(doy)
    std_val = float(std_raw) if std_raw is not None else 1.0
    z = storage_z_score(latest_fill, avg_val, std_val)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Current Fill", f"{latest_fill:.1f}%")
    c2.metric("vs 5yr Avg", f"{latest_dev:+.1f} pp")
    if target_dev is not None:
        c3.metric("vs Target", f"{target_dev:+.1f} pp")
    else:
        c3.metric("vs Target", "N/A")
    c4.metric("Days Ahead/Behind", f"{dab:+d}")
    c5.metric("Z-Score", f"{z:+.2f}")

    # Color-coded interpretation
    if z < -1.5:
        st.error(
            f"Storage is **{abs(latest_dev):.1f} pp below** the 5-year average (z-score {z:+.2f}). This is a significant deficit  - strongly supports the bullish thesis."
        )
    elif z < -0.5:
        st.warning(
            f"Storage is **{abs(latest_dev):.1f} pp below** the 5-year average (z-score {z:+.2f}). Slightly behind normal  - worth monitoring but not alarming yet."
        )
    elif z < 0.5:
        st.info(f"Storage is roughly in line with the 5-year average (z-score {z:+.2f}). No strong signal in either direction.")
    else:
        st.success(
            f"Storage is **{latest_dev:+.1f} pp above** the 5-year average (z-score {z:+.2f}). Comfortable position  - weakens the case for rising prices."
        )

    st.divider()

# --- Chart 1: Current fill vs 5-year avg vs target curve ---
st.subheader("Current Fill vs 5-Year Average vs Target")

fig1 = go.Figure()

# Green/Yellow/Red background bands for fill level zones
fig1.add_hrect(y0=80, y1=100, fillcolor="rgba(0,180,0,0.06)", line_width=0)
fig1.add_hrect(y0=60, y1=80, fillcolor="rgba(255,200,0,0.06)", line_width=0)
fig1.add_hrect(y0=0, y1=60, fillcolor="rgba(255,0,0,0.06)", line_width=0)

# Nov 1 deadline vertical line (day 305)
nov1_doy = datetime.date(current_year, 11, 1).timetuple().tm_yday
fig1.add_vline(x=nov1_doy, line_dash="dash", line_color="darkred", opacity=0.5, annotation_text="Nov 1 target", annotation_position="top left")

# 90% target horizontal line
fig1.add_hline(y=90, line_dash="dot", line_color="darkred", opacity=0.3, annotation_text="90%", annotation_position="right")

# 5-year average band
fig1.add_trace(
    go.Scatter(
        x=list(range(1, len(avg) + 1)),
        y=avg["avg_full_pct"],
        mode="lines",
        name="5yr Average",
        line={"dash": "dash", "color": "gray"},
    )
)

# Target curve
fig1.add_trace(
    go.Scatter(
        x=[d.timetuple().tm_yday for d in tc.index],
        y=tc["target_pct"],
        mode="lines",
        name="EU Target",
        line={"dash": "dot", "color": "red"},
    )
)

# Current year
if not current.empty:
    current_doy = pd.DatetimeIndex(current.index).day_of_year  # pyright: ignore[reportAttributeAccessIssue]
    fig1.add_trace(
        go.Scatter(
            x=current_doy.tolist(),
            y=current["full_pct"],
            mode="lines",
            name=str(current_year),
            line={"width": 3, "color": "#1f77b4"},
        )
    )

fig1.update_layout(
    xaxis_title="Day of Year",
    yaxis_title="Fill %",
    height=450,
    legend={"orientation": "h", "y": -0.15},
)
st.plotly_chart(fig1, width="stretch")

st.caption(
    "The solid blue line should stay above the red dotted EU target curve. Background bands: green (80%+) = comfortable, yellow (60-80%) = needs injection, red (<60%) = behind schedule. The vertical dashed line marks the November 1 deadline."
)

# --- Chart 2: Multi-year overlay ---
st.subheader("Multi-Year Overlay")

fig2 = go.Figure()

# ±1 std dev band around 5-year average
avg_plus = avg["avg_full_pct"] + avg["std_full_pct"]
avg_minus = avg["avg_full_pct"] - avg["std_full_pct"]
doy_range = list(range(1, len(avg) + 1))

fig2.add_trace(
    go.Scatter(
        x=doy_range + doy_range[::-1],
        y=avg_plus.tolist() + avg_minus.tolist()[::-1],
        fill="toself",
        fillcolor="rgba(128,128,128,0.15)",
        line={"width": 0},
        showlegend=True,
        name="5yr Avg +/- 1 Std Dev",
        hoverinfo="skip",
    )
)

fig2.add_trace(
    go.Scatter(
        x=doy_range,
        y=avg["avg_full_pct"],
        mode="lines",
        name="5yr Average",
        line={"dash": "dash", "color": "gray", "width": 2},
    )
)

colors = ["#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5"]

for i, year in enumerate(range(current_year - 5, current_year)):
    year_data = multi_year[multi_year.index.year == year]  # pyright: ignore[reportAttributeAccessIssue]
    if year_data.empty:
        continue
    doys = pd.DatetimeIndex(year_data.index).day_of_year  # pyright: ignore[reportAttributeAccessIssue]
    fig2.add_trace(
        go.Scatter(
            x=doys.tolist(),
            y=year_data["full_pct"],
            mode="lines",
            name=str(year),
            line={"color": colors[i % len(colors)]},
            opacity=0.6,
        )
    )

if not current.empty:
    current_doy = pd.DatetimeIndex(current.index).day_of_year  # pyright: ignore[reportAttributeAccessIssue]
    fig2.add_trace(
        go.Scatter(
            x=current_doy.tolist(),
            y=current["full_pct"],
            mode="lines",
            name=str(current_year),
            line={"width": 3, "color": "#1f77b4"},
        )
    )

fig2.update_layout(
    xaxis_title="Day of Year",
    yaxis_title="Fill %",
    height=450,
    legend={"orientation": "h", "y": -0.15},
)
st.plotly_chart(fig2, width="stretch")

st.caption(
    "The gray band shows the 'normal range' (5-year average +/- 1 standard deviation). If this year's blue line falls below the band, storage is unusually low for this time of year."
)
