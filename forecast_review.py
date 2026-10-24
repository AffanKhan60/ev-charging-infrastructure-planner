
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="EV Demand Forecast Evaluation",
    page_icon="⚡",
    layout="wide"
)

BASE_DIR = Path(__file__).resolve().parent
FILE = BASE_DIR / "reports" / "forecast_validation.csv"

st.title("EV Charging Demand Forecast Evaluation")

st.caption(
    "Historical test-set predictions for the public-area "
    "charging category. Not future forecasts."
)

if not FILE.exists():
    st.error("Run train_forecast.py first.")
    st.stop()

# Load forecast validation data
df = pd.read_csv(FILE)

df["hour_start"] = pd.to_datetime(
    df["hour_start"], errors="coerce"
)

columns = [
    "actual_sessions",
    "baseline_forecast",
    "ml_forecast"
]

for column in columns:
    df[column] = pd.to_numeric(
        df[column], errors="coerce"
    )

df = df.dropna(subset=["hour_start"] + columns)
df = df.sort_values("hour_start")

if df.empty:
    st.error("No valid forecast records found.")
    st.stop()

# Calculate performance
baseline_mae = (
    df["actual_sessions"] - df["baseline_forecast"]
).abs().mean()

ml_mae = (
    df["actual_sessions"] - df["ml_forecast"]
).abs().mean()

improvement = (
    (baseline_mae - ml_mae) / baseline_mae * 100
    if baseline_mae > 0 else 0
)

# KPI section
a, b, c = st.columns(3)

a.metric("Baseline MAE", f"{baseline_mae:.3f}")
b.metric("Random Forest MAE", f"{ml_mae:.3f}")
c.metric("MAE Improvement", f"{improvement:.2f}%")

st.divider()

# Show the last seven days of the test period
st.subheader("Hourly Forecast vs Actual Arrivals")

latest = df["hour_start"].max()
start = latest - pd.Timedelta(days=7)

recent = df[df["hour_start"] >= start].copy()

chart_data = recent.melt(
    id_vars="hour_start",
    value_vars=columns,
    var_name="Series",
    value_name="Session Starts"
)

fig = px.line(
    chart_data,
    x="hour_start",
    y="Session Starts",
    color="Series",
    title="Hourly Charging Session Starts — Test Period",
    labels={"hour_start": "Date and Time"}
)

st.plotly_chart(fig, use_container_width=True)

# Daily aggregated comparison
st.subheader("Daily Charging Session Forecast Comparison")

daily = (
    df.set_index("hour_start")[columns]
    .resample("D")
    .sum()
    .reset_index()
)

daily_chart = daily.melt(
    id_vars="hour_start",
    value_vars=columns,
    var_name="Series",
    value_name="Daily Session Starts"
)

fig_daily = px.line(
    daily_chart,
    x="hour_start",
    y="Daily Session Starts",
    color="Series",
    title="Daily Aggregated Predictions",
    labels={"hour_start": "Date"}
)

st.plotly_chart(fig_daily, use_container_width=True)

st.caption(
    "Daily totals sum the available hourly test observations; "
    "the first and last days may be partial."
)

# Actual vs predicted samples
st.subheader("Forecast Validation Data")

st.dataframe(
    df.tail(30),
    use_container_width=True,
    hide_index=True
)

st.info(
    "Next step: Validate data coverage and investigate "
    "model errors before developing site-level forecasts."
)
