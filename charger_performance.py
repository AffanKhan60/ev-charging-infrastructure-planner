
import sqlite3
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "ev_charging.db"

REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

# Load individual charging sessions
with sqlite3.connect(DB_FILE) as conn:
    df = pd.read_sql_query("""
        SELECT charger_id, location_type,
               start_time, energy_kwh
        FROM charging_sessions
    """, conn)

df["start_time"] = pd.to_datetime(
    df["start_time"], errors="coerce", format="mixed"
)

df["energy_kwh"] = pd.to_numeric(
    df["energy_kwh"], errors="coerce"
)

df = df.dropna(
    subset=["start_time", "energy_kwh"]
)

# Calculate individual charger statistics
summary = df.groupby("charger_id").agg(
    location_type=("location_type", "first"),
    total_sessions=("energy_kwh", "count"),
    total_energy_kwh=("energy_kwh", "sum"),
    avg_session_kwh=("energy_kwh", "mean"),
    first_session=("start_time", "min"),
    last_session=("start_time", "max")
).reset_index()

# Calculate observed span between first and last sessions
summary["observed_span_days"] = (
    summary["last_session"]
    - summary["first_session"]
).dt.total_seconds() / 86400

# Rank chargers by delivered energy
summary = summary.sort_values(
    "total_energy_kwh", ascending=False
)

# Export results
output = REPORT_DIR / "charger_performance.csv"
summary.to_csv(output, index=False)

print("\n--- CHARGER PERFORMANCE ANALYSIS ---")
print("Chargers analyzed:", len(summary))

print("\nTop 10 chargers by delivered energy:")
print(
    summary[
        ["charger_id", "location_type",
         "total_sessions", "total_energy_kwh"]
    ].head(10).to_string(index=False)
)

print("\nReport saved to:", output)
