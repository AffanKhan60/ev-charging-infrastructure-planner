
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

DATA_FILE = BASE_DIR / "data" / "ChargingRecords.csv"
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

# Load charging sessions
df = pd.read_csv(DATA_FILE, low_memory=False)

# Focus on public-area chargers
df = df[
    df["Location"].astype(str).str.strip().str.lower()
    == "public area"
].copy()

# Prepare measurements
df["start"] = pd.to_datetime(
    df["StartDatetime"], format="mixed", errors="coerce"
)

df["end"] = pd.to_datetime(
    df["EndDatetime"], format="mixed", errors="coerce"
)

df["energy_kwh"] = pd.to_numeric(
    df["Demand"], errors="coerce"
)

df["reported_duration"] = pd.to_numeric(
    df["Duration"], errors="coerce"
)

df["charger_type"] = pd.to_numeric(
    df["ChargerType"], errors="coerce"
)

# Calculate connection duration
df["connection_min"] = (
    df["end"] - df["start"]
).dt.total_seconds() / 60

# Apply existing quality rules
valid = df[
    df["connection_min"].between(1, 720)
    & (df["energy_kwh"] > 0)
    & (
        (df["connection_min"] - df["reported_duration"])
        .abs() <= 2
    )
    & df["charger_type"].isin([0, 1])
].copy()

if valid.empty:
    raise SystemExit("No valid records found.")

# Decode charger categories from research data dictionary
valid["charger_category"] = valid["charger_type"].map({
    0: "Slow",
    1: "Fast"
})

# Average energy delivery rate over connection time
valid["avg_kw"] = (
    valid["energy_kwh"] * 60
    / valid["connection_min"]
)

# Compare charging behavior
summary = valid.groupby(
    "charger_category"
).agg(
    sessions=("energy_kwh", "size"),
    median_energy_kwh=("energy_kwh", "median"),
    median_duration_min=("connection_min", "median"),
    p90_duration_min=(
        "connection_min",
        lambda x: x.quantile(0.90)
    ),
    median_avg_kw=("avg_kw", "median"),
    p90_avg_kw=(
        "avg_kw",
        lambda x: x.quantile(0.90)
    )
).reset_index()

summary = summary.round(2)

print("\n--- FAST VS SLOW CHARGING ---")
print(summary.to_string(index=False))

# Export comparison
output = REPORT_DIR / "charger_type_comparison.csv"

summary.to_csv(output, index=False)

print("\nReport saved to:", output)
print("Comparison completed!")
