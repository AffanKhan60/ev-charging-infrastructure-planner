
from pathlib import Path
import heapq

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "data" / "ChargingRecords.csv"
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

# Simulation assumptions
DAYS = 30
AVERAGE_ARRIVALS_PER_DAY = 25
CONNECTOR_SCENARIOS = [2, 4, 6, 8, 12]
MAX_CONNECTION_MINUTES = 720
WAIT_THRESHOLD_MINUTES = 15

rng = np.random.default_rng(42)

# Load real research data
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

df["reported_minutes"] = pd.to_numeric(
    df["Duration"], errors="coerce"
)

df["connection_minutes"] = (
    df["end"] - df["start"]
).dt.total_seconds() / 60

# Keep usable historical session durations
valid = df[
    df["start"].notna()
    & df["end"].notna()
    & df["reported_minutes"].notna()
    & (df["connection_minutes"] > 0)
    & (df["connection_minutes"] <= MAX_CONNECTION_MINUTES)
    & (
        (df["connection_minutes"] - df["reported_minutes"])
        .abs() <= 2
    )
].copy()

if len(valid) < 20:
    raise SystemExit("Insufficient valid sessions for simulation.")

print("Valid sessions for sampling:", len(valid))

# Learn the distribution of arrival hours
hour_counts = (
    valid["start"]
    .dt.hour
    .value_counts()
    .reindex(range(24), fill_value=0)
)

hour_probabilities = (
    hour_counts / hour_counts.sum()
).to_numpy()

durations = valid["connection_minutes"].to_numpy()

# Generate one common arrival sample for every scenario
arrivals = []

for day in range(DAYS):
    daily_count = rng.poisson(AVERAGE_ARRIVALS_PER_DAY)

    arrival_hours = rng.choice(
        24,
        size=daily_count,
        p=hour_probabilities
    )

    arrival_minutes = (
        day * 1440
        + arrival_hours * 60
        + rng.uniform(0, 60, size=daily_count)
    )

    sampled_durations = rng.choice(
        durations, size=daily_count
    )

    arrivals.extend(
        zip(arrival_minutes, sampled_durations)
    )

arrivals.sort(key=lambda item: item[0])

SIMULATION_END = DAYS * 1440

# Simulate first-come-first-served connector allocation
def simulate(number_of_connectors):
    available = [
        (0.0, connector)
        for connector in range(number_of_connectors)
    ]

    heapq.heapify(available)

    waiting_times = []
    busy_minutes = 0.0
    started_within_period = 0

    for arrival, duration in arrivals:
        free_at, connector = heapq.heappop(available)

        service_start = max(arrival, free_at)
        waiting_time = service_start - arrival
        service_end = service_start + duration

        waiting_times.append(waiting_time)

        if service_start < SIMULATION_END:
            started_within_period += 1

        busy_minutes += max(
            0.0,
            min(service_end, SIMULATION_END)
            - service_start
        )

        heapq.heappush(
            available, (service_end, connector)
        )

    waiting_times = np.array(waiting_times)

    return {
        "connectors": number_of_connectors,
        "arrivals": len(arrivals),
        "avg_wait_min": round(waiting_times.mean(), 1),
        "p95_wait_min": round(
            np.percentile(waiting_times, 95), 1
        ),
        "pct_wait_over_15min": round(
            (waiting_times > WAIT_THRESHOLD_MINUTES)
            .mean() * 100, 1
        ),
        "pct_started_in_period": round(
            started_within_period / len(arrivals) * 100, 1
        ),
        "connector_occupancy_pct": round(
            busy_minutes
            / (number_of_connectors * SIMULATION_END)
            * 100, 1
        )
    }

# Compare different connector configurations
results = pd.DataFrame([
    simulate(n) for n in CONNECTOR_SCENARIOS
])

print("\n--- CHARGING SITE SIMULATION ---")
print("Simulation days:", DAYS)
print("Average target arrivals/day:", AVERAGE_ARRIVALS_PER_DAY)
print("Simulated arrivals:", len(arrivals))

print("\n--- CONNECTOR SCENARIO COMPARISON ---")
print(results.to_string(index=False))

output_file = REPORT_DIR / "congestion_scenarios.csv"
results.to_csv(output_file, index=False)

print("\nReport saved to:", output_file)
