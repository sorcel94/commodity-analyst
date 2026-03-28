import datetime

import streamlit as st

from commodity_analyst.analysis.signals import compute_signals
from commodity_analyst.analysis.storage import five_year_average
from commodity_analyst.api.agsi import get_eu_storage
from commodity_analyst.api.alsi import get_eu_lng, get_unavailability

st.header("Imbalance Signals")
st.caption("Thesis validation: will EU gas prices rise next winter?")

with st.expander("How to read these signals"):
    st.markdown("""
Each signal checks one dimension of the EU gas supply/demand picture.

- **Green** = this factor **weakens** the bullish thesis (supply looks comfortable)
- **Yellow** = this factor is in a **warning zone** (worth monitoring)
- **Red** = this factor **supports** the thesis that prices will rise (supply stress)

The more red signals, the stronger the case for higher winter prices.
""")

_SIGNAL_EXPLAINERS: dict[str, str] = {
    "z_score": (
        "How far current storage fill is from the 5-year average for this date, "
        "measured in standard deviations. "
        "Red (< -1.5): severely below normal. Yellow (< -0.5): slightly below. Green: at or above normal."
    ),
    "injection_deficit": (
        "Extra GWh/day needed on top of current injection rate to reach 90% by Nov 1. "
        "Red (> 500 GWh/d): large gap, very hard to close. Yellow (> 0): some catch-up needed. Green (< 0): on track."
    ),
    "days_of_supply": (
        "How many days current gas in storage would last at the recent withdrawal rate. "
        "Red (< 30 days): critically low. Yellow (< 60 days): tight. Green (60+): comfortable buffer."
    ),
    "yoy_fill": (
        "Current fill level minus same-date fill last year, in percentage points. "
        "Red (< -5 pp): much worse than last year. Yellow (< 0 pp): slightly behind. Green (>= 0): same or better."
    ),
    "terminal_utilization": (
        "LNG terminal inventory as % of declared total maximum inventory (DTMI). "
        "Red (> 85%): terminals near full, limited import headroom. Yellow (> 70%): getting tight. "
        "Green (< 70%): plenty of capacity for more LNG."
    ),
    "outage_count": (
        "Number of LNG terminals currently reporting planned/unplanned unavailability. "
        "Red (> 10): widespread outages reducing import capacity. Yellow (> 3): moderate concern. "
        "Green (<= 3): normal operations."
    ),
}

current_year = datetime.date.today().year
today = datetime.date.today().isoformat()

# Fetch all required data
with st.spinner("Loading signal data..."):
    storage = get_eu_storage(f"{current_year}-01-01", today)
    storage_prev = get_eu_storage(f"{current_year - 1}-01-01", f"{current_year - 1}-12-31")
    multi_year = get_eu_storage(f"{current_year - 5}-01-01", f"{current_year - 1}-12-31")
    avg = five_year_average(multi_year)
    lng = get_eu_lng(f"{current_year}-03-01", today)
    unavail = get_unavailability()

if storage.empty:
    st.error("No storage data available.")
    st.stop()

signals = compute_signals(storage, storage_prev, avg, lng, unavail)

_EMOJI = {"green": "\U0001f7e2", "yellow": "\U0001f7e1", "red": "\U0001f534"}

# --- Signal cards ---
cols = st.columns(3)
for i, (key, sig) in enumerate(signals.items()):
    with cols[i % 3]:
        emoji = _EMOJI.get(sig["status"], "\u26aa")
        st.metric(label=sig["label"], value=sig["value"])
        st.markdown(f"{emoji} **{sig['status'].upper()}**")
        if key in _SIGNAL_EXPLAINERS:
            st.caption(_SIGNAL_EXPLAINERS[key])
        st.divider()

# --- Bottom Line ---
st.subheader("Bottom Line")

red_count = sum(1 for s in signals.values() if s["status"] == "red")
yellow_count = sum(1 for s in signals.values() if s["status"] == "yellow")
green_count = sum(1 for s in signals.values() if s["status"] == "green")

summary_text = f"**{red_count} red**, **{yellow_count} yellow**, **{green_count} green** out of {len(signals)} signals."

if red_count >= 3:
    st.error(
        f"Strong bullish signal. {summary_text} Multiple indicators point to supply stress heading into winter. The thesis that EU gas prices will rise is well-supported."
    )
elif red_count + yellow_count >= 3:
    st.warning(
        f"Moderate bullish signal. {summary_text} Several indicators are flashing caution. The thesis has partial support but isn't overwhelming."
    )
elif green_count >= 4:
    st.success(
        f"Bullish thesis weakened. {summary_text} Most indicators suggest supply is comfortable. The case for rising winter prices is currently weak."
    )
else:
    st.info(f"Mixed picture. {summary_text} No dominant direction  - keep monitoring as the injection season progresses.")

# --- Detailed interpretation ---
st.subheader("Signal Detail")

st.markdown(f"""
Key factors driving the outlook:

- **Storage Z-score** at **{signals["z_score"]["value"]}**: fill levels are
  {"well below" if signals["z_score"]["value"] < -1.5 else "slightly below" if signals["z_score"]["value"] < -0.5 else "at or above"}
  the 5-year average for this date.
- **Injection deficit** at **{signals["injection_deficit"]["value"]} GWh/d**:
  {"a large gap that will be very difficult to close" if signals["injection_deficit"]["value"] > 500 else "some catch-up injection is needed" if signals["injection_deficit"]["value"] > 0 else "injection is on pace to hit the 90% target"}.
- **YoY fill** at **{signals["yoy_fill"]["value"]} pp**: storage is
  {"significantly lower" if signals["yoy_fill"]["value"] < -5 else "slightly lower" if signals["yoy_fill"]["value"] < 0 else "the same or higher"}
  than the same date last year.
- **Days of supply**: **{signals["days_of_supply"]["value"]:.0f} days** at current withdrawal rates  -
  {"critically low" if signals["days_of_supply"]["value"] < 30 else "tight" if signals["days_of_supply"]["value"] < 60 else "comfortable buffer"}.
- **Terminal utilization** at **{signals["terminal_utilization"]["value"]}%**:
  {"near capacity  - limited room for extra LNG imports" if signals["terminal_utilization"]["value"] > 85 else "getting busy" if signals["terminal_utilization"]["value"] > 70 else "ample headroom for more LNG"}.
- **Active outages**: **{signals["outage_count"]["value"]}** terminals reporting unavailability  -
  {"widespread disruption to LNG imports" if signals["outage_count"]["value"] > 10 else "moderate concern" if signals["outage_count"]["value"] > 3 else "normal operations"}.
""")
