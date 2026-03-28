from __future__ import annotations

import datetime

import plotly.graph_objects as go
import streamlit as st

from commodity_analyst.api.alsi import get_eu_lng, get_terminal_data, get_terminal_listing

st.header("LNG Terminals")
st.caption("Are LNG imports supporting or constraining supply?")

with st.expander("What is LNG send-out?"):
    st.markdown("""
**Key terms:**
- **Send-out**  - the rate at which LNG is regasified and injected into the pipeline grid (GWh/day). Higher = more gas flowing into Europe.
- **LNG Inventory**  - the amount of LNG stored in terminal tanks (GWh), waiting to be regasified.
- **DTMI** (Declared Total Maximum Inventory)  - the maximum tank capacity of a terminal.
- **Utilization**  - inventory / DTMI. High utilization means terminals are near full and may struggle to accept more LNG cargoes.
""")

today = datetime.date.today().isoformat()
two_days_ago = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()

# Fetch latest EU LNG for context
eu_lng = get_eu_lng(two_days_ago, today)
listing = get_terminal_listing()

# --- KPI cards ---
if not eu_lng.empty:
    latest = eu_lng.iloc[-1]
    inv = float(latest["lng_inventory"])
    send_out = float(latest["send_out"])
    dtmi = float(latest["dtmi"])
    utilization = (inv / dtmi * 100.0) if dtmi > 0 else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("EU LNG Inventory", f"{inv:,.0f} GWh")
    c2.metric("EU Send-Out", f"{send_out:,.0f} GWh/d")
    c3.metric("Terminal Utilization", f"{utilization:.1f}%")

    if utilization > 85:
        st.error(f"Terminal utilization is **{utilization:.0f}%**  - near capacity. Limited room to accept additional LNG cargoes. Supports higher prices.")
    elif utilization > 70:
        st.warning(f"Terminal utilization is **{utilization:.0f}%**  - getting busy. Some buffer remains but not much headroom for surge imports.")
    else:
        st.success(f"Terminal utilization is **{utilization:.0f}%**  - ample capacity. Europe can absorb more LNG if needed.")

    st.divider()

# --- Terminal rankings table ---
st.subheader("Terminal Rankings")

if not listing.empty:
    st.dataframe(
        listing[["name", "country", "company_name", "type"]],
        width="stretch",
        hide_index=True,
    )

# --- EU LNG send-out trend ---
st.subheader("EU LNG Send-Out Trend")

if not eu_lng.empty:
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=eu_lng.index,
        y=eu_lng["send_out"],
        mode="lines+markers",
        name="EU Send-Out",
        line={"color": "#1f77b4"},
    ))
    fig1.update_layout(
        yaxis_title="Send-Out (GWh/d)",
        height=400,
    )
    st.plotly_chart(fig1, width="stretch")

    st.caption("Rising send-out = more LNG being regasified into the EU pipeline grid, easing supply pressure. Falling send-out = less LNG flowing in, which tightens the market.")

# --- Terminal drill-down ---
st.subheader("Terminal Drill-Down")

if not listing.empty:
    terminal_names = listing["name"].tolist()
    selected = st.selectbox("Select Terminal", terminal_names)

    if selected:
        row = listing[listing["name"] == selected].iloc[0]
        country_code = row["country"]
        company_eic = row["company_eic"]
        facility_eic = row["eic"]

        period_months = st.slider("Months of history", 1, 12, 3)
        from_date = (datetime.date.today() - datetime.timedelta(days=period_months * 30)).isoformat()

        try:
            terminal_df = get_terminal_data(country_code, company_eic, facility_eic, from_date, today)

            if not terminal_df.empty:
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(
                    x=terminal_df.index,
                    y=terminal_df["lng_inventory"],
                    mode="lines",
                    name="LNG Inventory (GWh)",
                    yaxis="y",
                ))
                fig2.add_trace(go.Scatter(
                    x=terminal_df.index,
                    y=terminal_df["send_out"],
                    mode="lines",
                    name="Send-Out (GWh/d)",
                    yaxis="y2",
                ))
                fig2.update_layout(
                    yaxis={"title": "LNG Inventory (GWh)"},
                    yaxis2={"title": "Send-Out (GWh/d)", "overlaying": "y", "side": "right"},
                    height=450,
                    legend={"orientation": "h", "y": -0.15},
                )
                st.plotly_chart(fig2, width="stretch")

                st.caption("Inventory falling while send-out rises = the terminal is actively regasifying. Inventory building with low send-out = tank storage is filling but gas isn't flowing yet.")
            else:
                st.warning("No data available for this terminal in the selected period.")
        except Exception as e:
            st.error(f"Error loading terminal data: {e}")
