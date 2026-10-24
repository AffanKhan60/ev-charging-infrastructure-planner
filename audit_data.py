
import sqlite3
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "ev_charging.db"
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

# Load charging sessions from SQLite
with sqlite3.connect(DB_FILE) as conn:
    df = pd.read_sql_query("""
        SELECT charger_id, start_time, energy_kwh
        FROM charging_sessions
        WHERE LOWER(TRIM(location_type)) = 'public area'
    """, conn)

df["start_time"] = pd.to_datetime(
    df["start_time"], format="mixed", errors="coerce"
)

df = df.dropna(subset=["start_time"])

if df.empty:
    raise SystemExit("No valid public-area sessions found.")

# Check hourly activity
df["hour_start"] = df["start_time"].dt.floor("h")

hourly_counts = df.groupby("hour_start").size()

timeline = pd.date_range(
    hourly_counts.index.min(),
    hourly_counts.index.max(),
    freq="h"
)

hourly_counts = hourly_counts.reindex(timeline, fill_value=0)

hours_without_starts = int((hourly_counts == 0).sum())

# Find longest period without recorded session starts
zero_hours = hourly_counts.eq(0)

runs = zero_hours.groupby(
    (zero_hours != zero_hours.shift()).cumsum()
).sum()

longest_gap = int(runs.max())

# Check daily activity and active chargers
df["date"] = df["start_time"].dt.floor("D")

daily = df.groupby("date").agg(
    sessions=("charger_id", "size"),
    active_chargers=("charger_id", "nunique"),
    energy_kwh=("energy_kwh", "sum"),
    hours_with_starts=("hour_start", "nunique")
)

all_days = pd.date_range(
    daily.index.min(),
    daily.index.max(),
    freq="D"
)

daily = daily.reindex(all_days, fill_value=0)
daily.index.name = "date"

# Export audit
output = REPORT_DIR / "data_coverage_audit.csv"
daily.to_csv(output)

print("\n--- DATA COVERAGE AUDIT ---")

print("First observation:", df["start_time"].min())
print("Last observation:", df["start_time"].max())

print("\nTotal timeline hours:", len(timeline))
print("Hours with recorded starts:", len(timeline) - hours_without_starts)
print("Hours without recorded starts:", hours_without_starts)

print(
    "Percentage without recorded starts:",
    round(hours_without_starts / len(timeline) * 100, 2), "%"
)

print("Longest period without starts:", longest_gap, "hours")

print("\n--- MONTHLY ACTIVITY ---")

monthly = daily.resample("MS").agg(
    sessions=("sessions", "sum"),
    avg_active_chargers=("active_chargers", "mean")
)

print(monthly.round(2).to_string())

print("\nAudit saved to:", output)
