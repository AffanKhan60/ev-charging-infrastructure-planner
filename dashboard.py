
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Application settings
st.set_page_config(
    page_title="EV Charging Intelligence",
    page_icon="⚡",
    layout="wide"
)

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "ev_charging.db"

st.title("⚡ EV Charging Intelligence Platform")
st.write(
    "Interactive analysis of real EV charging sessions "
    "for infrastructure planning."
)

st.caption(
    "Research dataset — not representative of the "
    "German charging market."
)

# Check database
if not DB_FILE.exists():
    st.error("Database not found. Run import_real_sessions.py.")
    st.stop()

# Load data
with sqlite3.connect(DB_FILE) as conn:
    df = pd.read_sql_query("""
        SELECT
            session_id,
            charger_id,
            location_type,
            charger_type,
            start_time,
            energy_kwh
        FROM charging_sessions
    """, conn)

if df.empty:
    st.error("No charging sessions found.")
    st.stop()

df["location_type"] = (
    df["location_type"].fillna("Unknown").replace("", "Unknown")
)

df["energy_kwh"] = pd.to_numeric(
    df["energy_kwh"], errors="coerce"
)

df["start_time"] = pd.to_datetime(
    df["start_time"], errors="coerce", format="mixed"
)

df = df.dropna(subset=["energy_kwh"])

# Sidebar filters
st.sidebar.header("Filters")

locations = sorted(df["location_type"].unique())

selected_locations = st.sidebar.multiselect(
    "Charging location",
    options=locations,
    default=locations
)

filtered = df[
    df["location_type"].isin(selected_locations)
].copy()

if filtered.empty:
    st.warning("Select at least one location.")
    st.stop()

# Calculate KPIs
sessions = len(filtered)
chargers = filtered["charger_id"].nunique()
total_energy = filtered["energy_kwh"].sum()
avg_energy = filtered["energy_kwh"].mean()

# KPI cards
st.subheader("Network Overview")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Charging Sessions", f"{sessions:,}")
c2.metric("Unique Chargers", f"{chargers:,}")
c3.metric("Delivered Energy", f"{total_energy:,.0f} kWh")
c4.metric("Average Session", f"{avg_energy:.1f} kWh")

st.divider()

# Location analysis
summary = filtered.groupby(
    "location_type", as_index=False
).agg(
    sessions=("session_id", "count"),
    energy_kwh=("energy_kwh", "sum"),
    chargers=("charger_id", "nunique"),
    avg_energy=("energy_kwh", "mean")
)

st.subheader("Charging Activity by Location")

left, right = st.columns(2)

with left:
    fig = px.bar(
        summary.sort_values("sessions", ascending=False),
        x="location_type",
        y="sessions",
        title="Charging Sessions by Location",
        labels={
            "location_type": "Location",
            "sessions": "Sessions"
        }
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    fig = px.bar(
        summary.sort_values("energy_kwh", ascending=False),
        x="location_type",
        y="energy_kwh",
        title="Delivered Energy by Location",
        labels={
            "location_type": "Location",
            "energy_kwh": "Energy (kWh)"
        }
    )
    st.plotly_chart(fig, use_container_width=True)

# Hourly session start analysis
st.subheader("Charging Session Start Patterns")

valid_times = filtered.dropna(subset=["start_time"]).copy()

valid_times["hour"] = valid_times["start_time"].dt.hour

hourly = valid_times.groupby(
    "hour", as_index=False
).agg(
    sessions=("session_id", "count")
)

fig = px.bar(
    hourly,
    x="hour",
    y="sessions",
    title="Session Starts by Hour of Day",
    labels={
        "hour": "Hour of Day",
        "sessions": "Number of Session Starts"
    }
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Session starts are not instantaneous charging power "
    "or hourly grid load."
)

# Data table
st.subheader("Location Performance Table")

st.dataframe(
    summary.round(2),
    use_container_width=True,
    hide_index=True
)

st.success("Dashboard loaded successfully!")
