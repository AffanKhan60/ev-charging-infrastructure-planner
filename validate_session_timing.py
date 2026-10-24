
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "data" / "ChargingRecords.csv"
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

# Load the original charging-session data
df = pd.read_csv(CSV_FILE, low_memory=False)

# Convert timestamps into datetime objects
df["start"] = pd.to_datetime(
    df["StartDatetime"], format="mixed", errors="coerce"
)

df["end"] = pd.to_datetime(
    df["EndDatetime"], format="mixed", errors="coerce"
)

df["duration_recorded"] = pd.to_numeric(
    df["Duration"], errors="coerce"
)

# Calculate actual connection time from timestamps
df["duration_calculated"] = (
    df["end"] - df["start"]
).dt.total_seconds() / 60

# Identify timing problems
invalid_timestamps = (
    df["start"].isna() | df["end"].isna()
)

negative_durations = (
    df["duration_calculated"] < 0
)

duration_mismatch = (
    (df["duration_calculated"] - df["duration_recorded"])
    .abs() > 2
)

# Analyze valid session intervals
valid = df[
    ~invalid_timestamps
    & ~negative_durations
    & (df["duration_calculated"] > 0)
].copy()

valid["charger_id"] = valid["ChargerID"].astype(str)

valid = valid.sort_values(
    ["charger_id", "start", "end"]
)

# Flag overlapping sessions on the same charger
valid["previous_end"] = (
    valid.groupby("charger_id")["end"]
    .transform(lambda x: x.cummax().shift(1))
)

valid["overlap"] = (
    valid["start"] < valid["previous_end"]
)

# Report findings
print("\n--- SESSION TIMING AUDIT ---")
print("Total source records:", len(df))
print("Invalid timestamps:", invalid_timestamps.sum())
print("Negative durations:", negative_durations.sum())
print("Duration mismatches:", duration_mismatch.sum())
print("Valid positive-length intervals:", len(valid))
print("Overlapping same-charger sessions:", valid["overlap"].sum())

# Save results
output = REPORT_DIR / "session_timing_audit.csv"

valid[
    ["charger_id", "start", "end",
     "duration_calculated", "duration_recorded",
     "overlap"]
].to_csv(output, index=False)

print("\nAudit saved to:", output)
