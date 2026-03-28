import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from commodity_analyst.api.agsi import get_eu_storage
from commodity_analyst.api.market import get_henry_hub, get_jkm, get_ttf

st.header("Market Benchmarks")
st.caption("What are current gas prices signaling?")

ttf = get_ttf("1y")
hh = get_henry_hub("1y")
jkm = get_jkm()

ttf_median = 0.0

# --- Price cards ---
c1, c2, c3 = st.columns(3)

with c1:
    if not ttf.empty:
        price = ttf["close"].iloc[-1]
        change = ttf["change"].iloc[-1]
        st.metric("TTF (EUR/MWh)", f"\u20ac{price:.2f}", f"{change:+.2f}")
        # 1yr range context
        ttf_min = float(ttf["close"].min())
        ttf_max = float(ttf["close"].max())
        ttf_median = float(ttf["close"].median())
        pctile = float((ttf["close"] < price).mean() * 100)
        st.caption(f"12m range: {ttf_min:.0f}\u2013{ttf_max:.0f} | Median: {ttf_median:.0f} | Current at **{pctile:.0f}th** percentile")
    else:
        st.metric("TTF (EUR/MWh)", "N/A")

with c2:
    if not hh.empty:
        price = hh["close"].iloc[-1]
        change = hh["change"].iloc[-1]
        st.metric("Henry Hub (USD/MMBtu)", f"${price:.3f}", f"{change:+.3f}")
        st.caption("US benchmark - a wide TTF-HH spread attracts LNG cargoes to Europe.")
    else:
        st.metric("Henry Hub (USD/MMBtu)", "N/A")

with c3:
    if not jkm.empty:
        jkm_eur = jkm["close"].iloc[-1]
        jkm_usd = jkm["close_usd_mmbtu"].iloc[-1]
        st.metric("JKM/Asia LNG (EUR/MWh)", f"\u20ac{jkm_eur:.1f}", f"${jkm_usd:.2f}/MMBtu")
        st.caption("Asian LNG benchmark - if JKM > TTF, LNG cargoes divert to Asia.")
    else:
        st.metric("JKM/Asia LNG (EUR/MWh)", "N/A")

st.divider()

# --- Overlay chart ---
st.subheader("12-Month Price Overlay")

fig1 = go.Figure()

if not ttf.empty:
    fig1.add_trace(
        go.Scatter(
            x=ttf.index,
            y=ttf["close"],
            mode="lines",
            name="TTF (EUR/MWh)",
            line={"color": "#1f77b4"},
        )
    )
    # TTF 12-month median reference line
    fig1.add_hline(
        y=ttf_median,
        line_dash="dot",
        line_color="#1f77b4",
        opacity=0.4,
        annotation_text=f"TTF Median: {ttf_median:.0f}",
        annotation_position="top left",
    )

if not hh.empty:
    fig1.add_trace(
        go.Scatter(
            x=hh.index,
            y=hh["close"],
            mode="lines",
            name="Henry Hub (USD/MMBtu)",
            yaxis="y2",
            line={"color": "#ff7f0e"},
        )
    )

if not jkm.empty:
    cutoff = datetime.date.today() - datetime.timedelta(days=365)
    jkm_recent = jkm[jkm.index >= str(cutoff)]
    if not jkm_recent.empty:
        fig1.add_trace(
            go.Scatter(
                x=jkm_recent.index,
                y=jkm_recent["close"],
                mode="lines+markers",
                name="JKM (EUR/MWh)",
                line={"color": "#2ca02c"},
            )
        )

fig1.update_layout(
    yaxis={"title": "EUR/MWh"},
    yaxis2={"title": "Henry Hub (USD/MMBtu)", "overlaying": "y", "side": "right"},
    height=500,
    legend={"orientation": "h", "y": -0.15},
)
st.plotly_chart(fig1, width="stretch")

st.caption(
    "TTF and JKM are both in EUR/MWh (left axis) so their spread is directly visible. Henry Hub (right axis) stays in USD/MMBtu. JKM is monthly FRED data with a 1-2 month publication lag."
)

# --- TTF vs Storage scatter ---
st.subheader("TTF Price vs EU Storage Fill")

current_year = datetime.date.today().year
try:
    storage = get_eu_storage(f"{current_year}-01-01", datetime.date.today().isoformat())
except Exception:
    storage = None

if storage is not None and not storage.empty and not ttf.empty:
    # Align on date
    storage_daily = storage[["full_pct"]].copy()
    storage_daily.index = storage_daily.index.date  # pyright: ignore[reportAttributeAccessIssue]
    ttf_daily = ttf[["close"]].copy()
    ttf_daily.index = ttf_daily.index.date  # pyright: ignore[reportAttributeAccessIssue]

    merged = storage_daily.join(ttf_daily, how="inner")

    if not merged.empty:
        # Correlation coefficient
        fill_series: pd.Series = merged["full_pct"]  # pyright: ignore[reportAssignmentType]
        close_series: pd.Series = merged["close"]  # pyright: ignore[reportAssignmentType]
        corr = float(fill_series.corr(close_series))

        fig2 = go.Figure()
        fig2.add_trace(
            go.Scatter(
                x=merged["full_pct"],
                y=merged["close"],
                mode="markers",
                marker={"color": "#1f77b4", "size": 5, "opacity": 0.6},
                name="Daily",
            )
        )
        # Annotate latest point
        fig2.add_trace(
            go.Scatter(
                x=[merged["full_pct"].iloc[-1]],
                y=[merged["close"].iloc[-1]],
                mode="markers+text",
                marker={"color": "red", "size": 12, "symbol": "star"},
                text=["Today"],
                textposition="top center",
                name="Current",
            )
        )

        # Median lines for quadrant reference
        med_fill = float(merged["full_pct"].median())
        med_price = float(merged["close"].median())
        fig2.add_hline(y=med_price, line_dash="dot", line_color="gray", opacity=0.3)
        fig2.add_vline(x=med_fill, line_dash="dot", line_color="gray", opacity=0.3)

        # Quadrant annotations
        fig2.add_annotation(
            x=med_fill - 5,
            y=med_price + (med_price * 0.15),
            text="Low fill + High price",
            showarrow=False,
            font={"size": 9, "color": "rgba(200,0,0,0.5)"},
        )
        fig2.add_annotation(
            x=med_fill + 5,
            y=med_price - (med_price * 0.15),
            text="High fill + Low price",
            showarrow=False,
            font={"size": 9, "color": "rgba(0,150,0,0.5)"},
        )

        fig2.update_layout(
            xaxis_title="EU Fill %",
            yaxis_title="TTF (EUR/MWh)",
            height=450,
        )
        st.plotly_chart(fig2, width="stretch")

        if corr < -0.5:
            st.caption(
                f"Correlation: **{corr:.2f}** (strong negative) - as storage falls, prices rise. This is the typical pattern: low fill = higher scarcity premium."
            )
        elif corr < -0.2:
            st.caption(f"Correlation: **{corr:.2f}** (moderate negative) - some inverse relationship between storage and prices, as expected.")
        elif corr < 0.2:
            st.caption(
                f"Correlation: **{corr:.2f}** (weak) - storage levels aren't the dominant price driver right now. Other factors (LNG flows, weather, geopolitics) matter more."
            )
        else:
            st.caption(
                f"Correlation: **{corr:.2f}** (positive) - unusual. Prices and storage are moving together, possibly driven by seasonal patterns or demand-side effects."
            )
else:
    st.info("Insufficient data for correlation chart.")
