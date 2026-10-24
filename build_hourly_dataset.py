
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "ev_charging.db"
OUTPUT_DIR = BASE_DIR / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

# Load session data from SQLite
with sqlite3.connect(DB_FILE) as conn:
    df = pd.read_sql_query("""
        SELECT
            location_type,
            start_time,
            energy_kwh
        FROM charging_sessions
    """, conn)

# Prepare timestamps
df["start_time"] = pd.to_datetime(
    df["start_time"],
    errors="coerce",
    format="mixed"
)

df["energy_kwh"] = pd.to_numeric(
    df["energy_kwh"],
    errors="coerce"
)

# Remove records with invalid dates or energy
df = df.dropna(subset=["start_time", "energy_kwh"])
df = df[df["energy_kwh"] >= 0].copy()

df["location_type"] = df["location_type"].fillna("unknown")

# Group charging session starts by hour
df["hour_start"] = df["start_time"].dt.floor("h")

hourly = (
    df.groupby(["location_type", "hour_start"])
    .agg(
        session_starts=("energy_kwh", "size"),
        session_energy_kwh=("energy_kwh", "sum")
    )
    .reset_index()
)

# Features for future machine learning models
hourly["hour"] = hourly["hour_start"].dt.hour
hourly["day_of_week"] = hourly["hour_start"].dt.dayofweek
hourly["month"] = hourly["hour_start"].dt.month

# Export dataset
output_file = OUTPUT_DIR / "hourly_session_arrivals.csv"
hourly.to_csv(output_file, index=False)

print("\n--- HOURLY CHARGING DATASET ---")
print("Valid source sessions:", len(df))
print("Hourly records:", len(hourly))
print("Location types:", hourly["location_type"].nunique())

print("\nSample:")
print(hourly.head(10).to_string(index=False))

print("\nDataset saved to:", output_file)
