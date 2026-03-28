import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from commodity_analyst.analysis.injection import injection_deficit, rolling_net_injection
from commodity_analyst.api.agsi import get_country_storage, get_eu_storage

st.header("Injection Analysis")
st.caption("Is the current injection pace sufficient to fill storage on time?")

current_year = datetime.date.today().year
today = datetime.date.today().isoformat()

# Fetch current and prior years
current = get_eu_storage(f"{current_year}-01-01", today)
prior_years: dict[int, pd.DataFrame] = {}
for yr in range(current_year - 3, current_year):
    prior_years[yr] = get_eu_storage(f"{yr}-01-01", f"{yr}-12-31")

# --- KPI cards ---
days_left = 0
required_rate = 0.0
if not current.empty:
    net_7d = rolling_net_injection(current, window=7)
    current_rate = float(net_7d.iloc[-1])
    latest_fill = float(current["full_pct"].iloc[-1])
    wgv = float(current["working_gas_volume"].iloc[-1])
    latest_date = pd.Timestamp(current.index[-1])  # pyright: ignore[reportArgumentType]
    nov_1 = pd.Timestamp(f"{current_year}-11-01")
    days_left = int(max((nov_1 - latest_date).days, 0))
    deficit = injection_deficit(latest_fill, 90.0, wgv, days_left, current_rate)
    required_rate = current_rate + deficit

    c1, c2, c3 = st.columns(3)
    c1.metric("Current 7d Injection", f"{current_rate:+.1f} GWh/d")
    c2.metric("Required Rate for 90%", f"{required_rate:.1f} GWh/d" if days_left > 0 else "Past deadline")
    c3.metric("Injection Deficit", f"{deficit:+.1f} GWh/d")

    if deficit > 500:
        st.error(
            f"Injection deficit is **{deficit:.0f} GWh/d**  - a large gap that will be very difficult to close in the {days_left} days remaining before November 1. Strongly supports higher prices."
        )
    elif deficit > 0:
        st.warning(f"Injection deficit is **{deficit:.0f} GWh/d**  - injection needs to pick up to hit 90%. {days_left} days remaining.")
    elif days_left > 0:
        st.success(
            f"On track  - current injection pace exceeds the required rate by **{abs(deficit):.0f} GWh/d**. {days_left} days remaining before November 1."
        )
    else:
        st.info("The November 1 deadline has passed.")

    st.divider()

# --- Chart 1: Rolling 7-day net injection vs prior years ---
st.subheader("Rolling 7-Day Net Injection")

fig1 = go.Figure()
colors = ["#aec7e8", "#ffbb78", "#98df8a"]

for i, (yr, df) in enumerate(prior_years.items()):
    if df.empty:
        continue
    net = rolling_net_injection(df, window=7)
    doys = pd.DatetimeIndex(df.index).day_of_year  # pyright: ignore[reportAttributeAccessIssue]
    fig1.add_trace(
        go.Scatter(
            x=doys.tolist(),
            y=net,
            mode="lines",
            name=str(yr),
            line={"color": colors[i % len(colors)]},
            opacity=0.6,
        )
    )

if not current.empty:
    net_current = rolling_net_injection(current, window=7)
    current_doy = pd.DatetimeIndex(current.index).day_of_year  # pyright: ignore[reportAttributeAccessIssue]
    fig1.add_trace(
        go.Scatter(
            x=current_doy.tolist(),
            y=net_current,
            mode="lines",
            name=str(current_year),
            line={"width": 3, "color": "#1f77b4"},
        )
    )

    # Required rate reference line
    if days_left > 0:
        fig1.add_hline(
            y=required_rate,
            line_dash="dot",
            line_color="red",
            opacity=0.6,
            annotation_text=f"Required: {required_rate:.0f} GWh/d",
            annotation_position="right",
        )

fig1.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
fig1.update_layout(
    xaxis_title="Day of Year",
    yaxis_title="Net Injection (GWh/d)",
    height=450,
    legend={"orientation": "h", "y": -0.15},
)
st.plotly_chart(fig1, width="stretch")

st.caption(
    "Above zero = net injection (storage filling). Below zero = net withdrawal (storage draining). The red dotted line shows the daily injection rate needed to reach 90% by November 1. The blue line should stay above it."
)

# --- Chart 2: Current vs prior week injection ---
st.subheader("Current vs Prior Week")

if not current.empty and len(current) >= 14:
    current_week = current.tail(7)
    prior_week = current.iloc[-14:-7]

    fig2 = go.Figure()
    days_labels = [str(d.date()) for d in current_week.index]

    fig2.add_trace(
        go.Bar(
            x=days_labels,
            y=current_week["injection"],
            name="Current Week",
            marker_color="#1f77b4",
        )
    )
    fig2.add_trace(
        go.Bar(
            x=days_labels,
            y=prior_week["injection"].values,
            name="Prior Week",
            marker_color="#aec7e8",
        )
    )
    fig2.update_layout(
        barmode="group",
        yaxis_title="Injection (GWh/d)",
        height=400,
        legend={"orientation": "h", "y": -0.15},
    )
    st.plotly_chart(fig2, width="stretch")

    st.caption("Taller blue bars than gray = injection is accelerating week-over-week. Shrinking bars = injection pace is slowing.")
else:
    st.info("Not enough data for week-over-week comparison.")

# --- Chart 3: Country breakdown ---
st.subheader("Country Injection Breakdown (Top 5)")

top_countries = ["DE", "NL", "IT", "FR", "AT"]

# Fetch last 7 days for each country
country_data: dict[str, float] = {}
week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
for code in top_countries:
    try:
        df = get_country_storage(code, week_ago, today)
        if not df.empty:
            country_data[code] = float(df["injection"].mean())
    except Exception:
        pass

if country_data:
    fig3 = go.Figure()
    fig3.add_trace(
        go.Bar(
            x=list(country_data.keys()),
            y=list(country_data.values()),
            marker_color=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"],
        )
    )
    fig3.update_layout(
        yaxis_title="Avg Injection (GWh/d, 7d)",
        height=400,
    )
    st.plotly_chart(fig3, width="stretch")

    st.caption(
        "Germany (DE) and Italy (IT) are the largest storage markets. If their injection slows, it's harder for the EU aggregate to keep pace."
    )
else:
    st.info("Country data unavailable.")
