
import heapq
from pathlib import Path

import numpy as np
import pandas as pd

# Project paths
BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "data" / "ChargingRecords.csv"
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

# Simulation settings
DAYS = 30
DEMAND_SCENARIOS = [15, 25, 35]
CONNECTOR_SCENARIOS = [4, 6, 8, 12]
REPETITIONS = 20
WAIT_THRESHOLD = 15
SIM_END = DAYS * 1440

# Load historical charging data
df = pd.read_csv(CSV_FILE, low_memory=False)

df = df[
    df["Location"].astype(str).str.lower().str.strip()
    == "public area"
].copy()

df["start"] = pd.to_datetime(
    df["StartDatetime"], format="mixed", errors="coerce"
)

df["end"] = pd.to_datetime(
    df["EndDatetime"], format="mixed", errors="coerce"
)

df["reported_duration"] = pd.to_numeric(
    df["Duration"], errors="coerce"
)

df["duration_min"] = (
    df["end"] - df["start"]
).dt.total_seconds() / 60

# Retain plausible, consistent connection durations
valid = df[
    df["start"].notna()
    & df["duration_min"].between(1, 720)
    & (
        (df["duration_min"] - df["reported_duration"])
        .abs() <= 2
    )
].copy()

if len(valid) < 20:
    raise SystemExit("Insufficient valid charging data.")

# Historical arrival-hour distribution
hour_counts = (
    valid["start"]
    .dt.hour
    .value_counts()
    .reindex(range(24), fill_value=0)
    .to_numpy(dtype=float)
)

hour_probs = hour_counts / hour_counts.sum()
duration_pool = valid["duration_min"].to_numpy()

# Generate arrivals for one simulation run
def generate_arrivals(rng, average_daily):
    arrivals = []

    for day in range(DAYS):
        count = rng.poisson(average_daily)

        hours = rng.choice(
            24, size=count, p=hour_probs
        )

        times = (
            day * 1440
            + hours * 60
            + rng.uniform(0, 60, count)
        )

        durations = rng.choice(
            duration_pool, size=count
        )

        arrivals.extend(
            zip(times.tolist(), durations.tolist())
        )

    return sorted(arrivals)


# Simulate connector availability and queues
def simulate(arrivals, connectors):
    available = [0.0] * connectors
    heapq.heapify(available)

    waits = []
    occupied_minutes = 0
    not_started = 0

    for arrival, duration in arrivals:
        free_at = heapq.heappop(available)

        service_start = max(arrival, free_at)
        service_end = service_start + duration

        wait = service_start - arrival
        waits.append(wait)

        if service_start >= SIM_END:
            not_started += 1

        occupied_minutes += max(
            0,
            min(service_end, SIM_END) - service_start
        )

        heapq.heappush(available, service_end)

    waits = np.array(waits)

    return {
        "avg_wait_min": waits.mean(),
        "p95_wait_min": np.percentile(waits, 95),
        "pct_wait_over_15": (
            (waits > WAIT_THRESHOLD).mean() * 100
        ),
        "occupancy_pct": (
            occupied_minutes
            / (connectors * SIM_END) * 100
        ),
        "pct_not_started": (
            not_started / len(arrivals) * 100
        )
    }


# Perform demand sensitivity analysis
records = []

for daily_demand in DEMAND_SCENARIOS:

    for run in range(REPETITIONS):

        rng = np.random.default_rng(
            1000 + daily_demand * 100 + run
        )

        # Same arrivals for every connector comparison
        arrivals = generate_arrivals(rng, daily_demand)

        for connectors in CONNECTOR_SCENARIOS:

            result = simulate(arrivals, connectors)

            records.append({
                "cars_per_day": daily_demand,
                "connectors": connectors,
                **result
            })

results = pd.DataFrame(records)

# Average performance across repetitions
summary = (
    results.groupby(["cars_per_day", "connectors"])
    .agg(
        avg_wait_min=("avg_wait_min", "mean"),
        avg_p95_wait_min=("p95_wait_min", "mean"),
        pct_wait_over_15=("pct_wait_over_15", "mean"),
        occupancy_pct=("occupancy_pct", "mean"),
        pct_not_started=("pct_not_started", "mean")
    )
    .reset_index()
)

summary = summary.round(1)

# Export report
output = REPORT_DIR / "demand_sensitivity.csv"
summary.to_csv(output, index=False)

print("\n--- EV CHARGING DEMAND SENSITIVITY ---")
print("Simulation duration:", DAYS, "days")
print("Repetitions per scenario:", REPETITIONS)

print("\n--- SCENARIO RESULTS ---")
print(summary.to_string(index=False))

print("\nReport saved to:", output)
print("Sensitivity analysis completed!")
