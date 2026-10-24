
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ==========================================
# APPLICATION SETUP
# ==========================================

st.set_page_config(
    page_title="EV Charging Expansion Planner",
    page_icon="⚡",
    layout="wide"
)

BASE = Path(__file__).resolve().parent
FILE = BASE / "reports" / "fast_charging_scenarios.csv"

st.title("⚡ EV Charging Infrastructure Expansion Planner")

st.caption(
    "Hardware-aware site planning | Synthetic demand | "
    "Research-derived charging behavior"
)

if not FILE.exists():
    st.error("Run grid_aware_simulation.py first.")
    st.stop()

df = pd.read_csv(FILE)

required = [
    "grid_kw", "chargers", "connectors",
    "connectors_per_charger", "cabinet_limit_kw",
    "avg_wait_min", "p95_wait_min",
    "known_wait_over_15_pct", "occupancy_pct",
    "completed_pct", "queued_at_end",
    "delivered_energy_pct", "peak_grid_draw_kw"
]

missing = [c for c in required if c not in df.columns]

if missing:
    st.error(f"Missing CSV columns: {missing}")
    st.stop()

# ==========================================
# PLANNING CONTROLS
# ==========================================

st.sidebar.header("Engineering Configuration")

grid_options = sorted(df["grid_kw"].unique().tolist())

default_index = (
    grid_options.index(150)
    if 150 in grid_options else 0
)

grid = st.sidebar.selectbox(
    "Available site grid power (kW)",
    grid_options,
    index=default_index
)

max_long_wait = st.sidebar.slider(
    "Maximum drivers waiting >15 min (%)",
    0.0, 30.0, 5.0, 0.5
)

max_p95 = st.sidebar.slider(
    "Maximum P95 waiting time (min)",
    0, 120, 15, 5
)

# ==========================================
# SELECT SCENARIO
# ==========================================

scenario = df[df["grid_kw"] == grid].copy()
scenario = scenario.sort_values("chargers")

scenario["meets_target"] = (
    (scenario["known_wait_over_15_pct"] <= max_long_wait)
    & (scenario["p95_wait_min"] <= max_p95)
    & (scenario["completed_pct"] >= 99)
    & (scenario["queued_at_end"] == 0)
    & (scenario["delivered_energy_pct"] >= 99.5)
)

scenario["configuration"] = (
    scenario["chargers"].astype(int).astype(str)
    + " chargers / "
    + scenario["connectors"].astype(int).astype(str)
    + " connectors"
)

# ==========================================
# SITE OVERVIEW
# ==========================================

st.subheader("Site Engineering Configuration")

a, b, c, d = st.columns(4)

a.metric("Available Grid Power", f"{grid:g} kW")
b.metric(
    "Connectors per Charger",
    int(scenario["connectors_per_charger"].iloc[0])
)
c.metric(
    "Power per Charging Unit",
    f"{scenario['cabinet_limit_kw'].iloc[0]:g} kW"
)
d.metric("Mean Demand", "25 EVs/day")

st.divider()

# ==========================================
# CONFIGURATION RECOMMENDATION
# ==========================================

valid = scenario[scenario["meets_target"]]

st.subheader("Preliminary Capacity Assessment")

if not valid.empty:
    selected = valid.iloc[0]

    st.success(
        f"Smallest tested configuration meeting the "
        f"selected criteria: "
        f"{int(selected['chargers'])} physical chargers "
        f"with {int(selected['connectors'])} connectors."
    )

    a, b, c = st.columns(3)

    a.metric(
        "Average Customer Wait",
        f"{selected['avg_wait_min']:.1f} min"
    )

    b.metric(
        "Long-Wait Probability",
        f"{selected['known_wait_over_15_pct']:.1f}%"
    )

    c.metric(
        "Simulated Peak Grid Draw",
        f"{selected['peak_grid_draw_kw']:.1f} kW"
    )

else:
    st.warning(
        "No tested hardware configuration meets "
        "all selected service criteria."
    )

st.caption(
    "Based on one synthetic simulation run. "
    "Not a validated equipment purchase or "
    "grid-connection recommendation."
)

# ==========================================
# CUSTOMER WAITING PERFORMANCE
# ==========================================

st.subheader("Customer Waiting Time")

fig_wait = px.bar(
    scenario,
    x="configuration",
    y="avg_wait_min",
    text="avg_wait_min",
    title="Average Waiting Time by Hardware Configuration",
    labels={
        "configuration": "Charging Site Configuration",
        "avg_wait_min": "Average Waiting Time (min)"
    }
)

fig_wait.update_traces(textposition="outside")

st.plotly_chart(fig_wait, use_container_width=True)

# ==========================================
# CUSTOMER SERVICE PERFORMANCE
# ==========================================

st.subheader("Customer Service Quality")

fig_service = px.bar(
    scenario,
    x="configuration",
    y="known_wait_over_15_pct",
    text="known_wait_over_15_pct",
    title="Drivers Waiting More Than 15 Minutes",
    labels={
        "configuration": "Charging Site Configuration",
        "known_wait_over_15_pct": "Drivers (%)"
    }
)

fig_service.add_hline(
    y=max_long_wait,
    line_dash="dash",
    annotation_text="Service target"
)

st.plotly_chart(fig_service, use_container_width=True)

# ==========================================
# ELECTRICAL PERFORMANCE
# ==========================================

st.subheader("Electrical Power Requirements")

fig_power = px.bar(
    scenario,
    x="configuration",
    y="peak_grid_draw_kw",
    text="peak_grid_draw_kw",
    title="Simulated Peak Grid Power",
    labels={
        "configuration": "Charging Site Configuration",
        "peak_grid_draw_kw": "Grid Power (kW)"
    }
)

fig_power.add_hline(
    y=grid,
    line_dash="dash",
    annotation_text="Available grid power"
)

st.plotly_chart(fig_power, use_container_width=True)

st.caption(
    "Simulated peak is based on one-minute energy delivery. "
    "It is not a measured instantaneous demand peak."
)

# ==========================================
# ENGINEERING COMPARISON
# ==========================================

st.subheader("Full Configuration Comparison")

display = scenario[[
    "chargers",
    "connectors",
    "avg_wait_min",
    "p95_wait_min",
    "known_wait_over_15_pct",
    "occupancy_pct",
    "completed_pct",
    "peak_grid_draw_kw",
    "meets_target"
]].copy()

display["meets_target"] = display["meets_target"].map({
    True: "Yes",
    False: "No"
})

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True
)

with st.expander("Engineering Assumptions"):
    st.write(
        "One charging unit has two connectors. "
        "Each unit has a shared 75 kW power limit, "
        "and each connector has a 50 kW maximum."
    )
    st.write(
        "The simulation uses historical fast-category "
        "energy and connection durations, with synthetic "
        "vehicle arrivals averaging 25 per day."
    )
    st.write(
        "Equal power sharing is assumed. Vehicle-specific "
        "charging curves, downtime, auxiliary site loads, "
        "and investment costs are not yet modeled."
    )

st.info(
    "Next: Improve scenario robustness, introduce "
    "configurable charging hardware, and compare "
    "infrastructure investment options."
)
