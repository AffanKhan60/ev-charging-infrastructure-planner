
"""
EV Charging Site Planner
Hardware-Aware Monte Carlo Simulation

Purpose:
Evaluate charging infrastructure configurations
across multiple synthetic demand scenarios.
"""

from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd


# ==========================================
# 1. PROJECT CONFIGURATION
# ==========================================

BASE = Path(__file__).resolve().parent

DATA_FILE = BASE / "data" / "ChargingRecords.csv"

REPORT_DIR = BASE / "reports"
REPORT_DIR.mkdir(exist_ok=True)

# Simulation settings
DAYS = 30
MEAN_CARS_PER_DAY = 25
REPETITIONS = 20

# Charging hardware assumptions
CONNECTORS_PER_CHARGER = 2
CABINET_MAX_KW = 75.0
CONNECTOR_MAX_KW = 50.0

# Scenarios
GRID_OPTIONS_KW = [75, 150, 300]
CHARGER_OPTIONS = [1, 2, 3, 4]

# Customer service requirements
MAX_LONG_WAIT_PCT = 5.0
MAX_P95_WAIT_MIN = 15.0
MIN_COMPLETION_PCT = 99.0
MIN_DELIVERED_ENERGY_PCT = 99.5

WAIT_LIMIT_MIN = 15

SIM_END = DAYS * 24 * 60

EPS = 1e-9


# ==========================================
# 2. LOAD HISTORICAL CHARGING DATA
# ==========================================

if not DATA_FILE.exists():
    raise SystemExit(
        f"Missing source data: {DATA_FILE}"
    )

source = pd.read_csv(
    DATA_FILE,
    low_memory=False
)

source["start"] = pd.to_datetime(
    source["StartDatetime"],
    format="mixed",
    errors="coerce"
)

source["end"] = pd.to_datetime(
    source["EndDatetime"],
    format="mixed",
    errors="coerce"
)

source["energy"] = pd.to_numeric(
    source["Demand"],
    errors="coerce"
)

source["reported_minutes"] = pd.to_numeric(
    source["Duration"],
    errors="coerce"
)

source["charger_type"] = pd.to_numeric(
    source["ChargerType"],
    errors="coerce"
)

source["dwell_minutes"] = (
    source["end"] - source["start"]
).dt.total_seconds() / 60

# Only public-area fast-category sessions
valid = source.loc[
    source["Location"]
    .astype(str)
    .str.strip()
    .str.lower()
    .eq("public area")

    & source["charger_type"].eq(1)

    & source["dwell_minutes"].between(1, 720)

    & source["energy"].gt(0)

    & (
        source["dwell_minutes"]
        - source["reported_minutes"]
    ).abs().le(2)
].copy()

if len(valid) < 20:
    raise SystemExit(
        "Not enough valid fast-charging sessions."
    )


# ==========================================
# 3. LEARN CHARGING BEHAVIOR
# ==========================================

arrival_counts = (
    valid["start"]
    .dt.hour
    .value_counts()
    .reindex(range(24), fill_value=0)
)

hour_probabilities = (
    arrival_counts / arrival_counts.sum()
).to_numpy()

# Preserve historical relationship
# between energy and connection duration
session_pairs = valid[
    ["energy", "dwell_minutes"]
].to_numpy(dtype=float)


# ==========================================
# 4. GENERATE SYNTHETIC MONTHS
# ==========================================

def generate_arrivals(seed):

    rng = np.random.default_rng(seed)

    events = []

    for day in range(DAYS):

        number_of_cars = int(
            rng.poisson(MEAN_CARS_PER_DAY)
        )

        hours = rng.choice(
            24,
            size=number_of_cars,
            p=hour_probabilities
        )

        arrival_times = (
            day * 1440
            + hours * 60
            + rng.integers(
                0, 60, size=number_of_cars
            )
        )

        sample_indices = rng.integers(
            0,
            len(session_pairs),
            size=number_of_cars
        )

        for minute, index in zip(
            arrival_times,
            sample_indices
        ):

            energy, dwell = session_pairs[index]

            events.append((
                int(minute),
                float(energy),
                float(dwell)
            ))

    events.sort(key=lambda x: x[0])

    return events


# ==========================================
# 5. HARDWARE-AWARE SIMULATION
# ==========================================

def simulate(events, chargers, grid_kw):

    connectors = (
        chargers * CONNECTORS_PER_CHARGER
    )

    queue = deque()
    active = []

    next_arrival = 0
    completed = 0
    occupied_min = 0

    delivered_total = 0.0
    peak_grid_kw = 0.0

    waits = []

    total_requested = sum(
        event[1] for event in events
    )

    for minute in range(SIM_END):

        # ----------------------------------
        # A. Register vehicle arrivals
        # ----------------------------------

        while (
            next_arrival < len(events)
            and events[next_arrival][0] <= minute
        ):

            queue.append(
                events[next_arrival]
            )

            next_arrival += 1

        # ----------------------------------
        # B. Release completed vehicles
        # ----------------------------------

        remaining = []

        for car in active:

            energy_complete = (
                car["energy_left"] <= EPS
            )

            dwell_complete = (
                minute >= car["release_after"]
            )

            if energy_complete and dwell_complete:
                completed += 1

            else:
                remaining.append(car)

        active = remaining

        # ----------------------------------
        # C. Allocate available connectors
        # ----------------------------------

        while queue and len(active) < connectors:

            count_by_charger = [0] * chargers

            for car in active:

                count_by_charger[
                    car["charger"]
                ] += 1

            available = [
                c for c in range(chargers)
                if count_by_charger[c]
                < CONNECTORS_PER_CHARGER
            ]

            if not available:
                break

            # Prefer least occupied charger
            charger = min(
                available,
                key=lambda c: (
                    count_by_charger[c],
                    c
                )
            )

            arrival, energy, dwell = (
                queue.popleft()
            )

            waits.append(
                minute - arrival
            )

            active.append({
                "charger": charger,
                "energy_left": energy,
                "release_after": minute + dwell
            })

        # ----------------------------------
        # D. Identify charging vehicles
        # ----------------------------------

        charging = [
            car for car in active
            if car["energy_left"] > EPS
        ]

        allocations = []

        # ----------------------------------
        # E. Apply cabinet power limits
        # ----------------------------------

        for charger in range(chargers):

            group = [
                car for car in charging
                if car["charger"] == charger
            ]

            if group:

                per_car_kw = min(
                    CONNECTOR_MAX_KW,
                    CABINET_MAX_KW / len(group)
                )

                allocations.extend(
                    (car, per_car_kw)
                    for car in group
                )

        # ----------------------------------
        # F. Apply site grid-power limit
        # ----------------------------------

        requested_kw = sum(
            power_kw
            for _, power_kw in allocations
        )

        if requested_kw > 0:

            scale = min(
                1.0,
                grid_kw / requested_kw
            )

        else:
            scale = 1.0

        delivered_this_minute = 0.0

        for car, allocated_kw in allocations:

            actual_kw = (
                allocated_kw * scale
            )

            energy = min(
                car["energy_left"],
                actual_kw / 60
            )

            car["energy_left"] -= energy

            delivered_this_minute += energy

        # ----------------------------------
        # G. Validate electrical constraints
        # ----------------------------------

        actual_grid_kw = (
            delivered_this_minute * 60
        )

        assert (
            actual_grid_kw <= grid_kw + 1e-6
        ), "Grid power limit exceeded."

        peak_grid_kw = max(
            peak_grid_kw,
            actual_grid_kw
        )

        delivered_total += (
            delivered_this_minute
        )

        occupied_min += len(active)

    # ======================================
    # 6. FINAL ACCOUNTING
    # ======================================

    queued_at_end = len(queue)
    active_at_end = len(active)

    undelivered_kwh = (
        sum(
            max(car["energy_left"], 0.0)
            for car in active
        )
        + sum(
            event[1] for event in queue
        )
    )

    # Check all vehicles are accounted for
    assert (
        completed
        + active_at_end
        + queued_at_end
        == len(events)
    ), "Session accounting failed."

    # Check energy conservation
    assert np.isclose(
        delivered_total + undelivered_kwh,
        total_requested,
        atol=0.001
    ), "Energy balance failed."

    started_waits = np.asarray(waits)

    # Drivers waiting over 15 minutes
    long_waits = sum(
        wait > WAIT_LIMIT_MIN
        for wait in waits
    )

    long_waits += sum(
        SIM_END - arrival > WAIT_LIMIT_MIN
        for arrival, _, _ in queue
    )

    n = len(events)

    return {
        "grid_kw": grid_kw,

        "chargers": chargers,

        "connectors": connectors,

        "connectors_per_charger":
            CONNECTORS_PER_CHARGER,

        "cabinet_limit_kw": CABINET_MAX_KW,

        "arrivals": n,

        "avg_wait_min": (
            float(started_waits.mean())
            if len(waits) else 0.0
        ),

        "p95_wait_min": (
            float(
                np.percentile(
                    started_waits, 95
                )
            )
            if len(waits) else 0.0
        ),

        "known_wait_over_15_pct": (
            100 * long_waits / n
            if n else 0.0
        ),

        "occupancy_pct": (
            100 * occupied_min
            / (connectors * SIM_END)
        ),

        "completed_pct": (
            100 * completed / n
            if n else 0.0
        ),

        "queued_at_end": queued_at_end,

        "active_at_end": active_at_end,

        "delivered_energy_pct": (
            100 * delivered_total
            / total_requested
            if total_requested else 0.0
        ),

        "peak_grid_draw_kw": peak_grid_kw,

        "undelivered_kwh": undelivered_kwh
    }


# ==========================================
# 7. SERVICE QUALITY CHECK
# ==========================================

def meets_service_target(result):

    return (
        result["known_wait_over_15_pct"]
        <= MAX_LONG_WAIT_PCT

        and result["p95_wait_min"]
        <= MAX_P95_WAIT_MIN

        and result["completed_pct"]
        >= MIN_COMPLETION_PCT

        and result["delivered_energy_pct"]
        >= MIN_DELIVERED_ENERGY_PCT

        and result["queued_at_end"] == 0
    )


# ==========================================
# 8. ORIGINAL DASHBOARD DATA
# ==========================================

# Keep original dashboard compatible
reference_events = generate_arrivals(
    seed=42
)

reference_rows = [
    simulate(
        reference_events,
        chargers,
        grid
    )

    for grid in GRID_OPTIONS_KW
    for chargers in CHARGER_OPTIONS
]

reference = pd.DataFrame(
    reference_rows
).round(2)

reference_path = (
    REPORT_DIR / "fast_charging_scenarios.csv"
)

reference.to_csv(
    reference_path,
    index=False
)


# ==========================================
# 9. MONTE CARLO SIMULATION
# ==========================================

records = []

for run in range(REPETITIONS):

    # Each run generates a different month
    events = generate_arrivals(
        seed=1000 + run
    )

    # Compare configurations using
    # exactly the same arrivals per run
    for grid in GRID_OPTIONS_KW:

        for chargers in CHARGER_OPTIONS:

            result = simulate(
                events,
                chargers,
                grid
            )

            records.append({
                "run": run + 1,

                "grid_kw": grid,

                "chargers": chargers,

                "connectors":
                    result["connectors"],

                "arrivals":
                    result["arrivals"],

                "avg_wait_min":
                    result["avg_wait_min"],

                "p95_wait_min":
                    result["p95_wait_min"],

                "long_wait_pct":
                    result["known_wait_over_15_pct"],

                "completed_pct":
                    result["completed_pct"],

                "meets_target": int(
                    meets_service_target(result)
                )
            })


# ==========================================
# 10. AGGREGATE RESULTS
# ==========================================

runs = pd.DataFrame(records)

summary = (
    runs.groupby(
        ["grid_kw", "chargers", "connectors"],
        as_index=False
    )
    .agg(
        mean_arrivals=(
            "arrivals",
            "mean"
        ),

        mean_wait_min=(
            "avg_wait_min",
            "mean"
        ),

        p90_long_wait_pct=(
            "long_wait_pct",
            lambda x: x.quantile(0.90)
        ),

        p90_p95_wait_min=(
            "p95_wait_min",
            lambda x: x.quantile(0.90)
        ),

        mean_completed_pct=(
            "completed_pct",
            "mean"
        ),

        service_pass_rate_pct=(
            "meets_target",
            lambda x: 100 * x.mean()
        )
    )
    .round(2)
)


# ==========================================
# 11. SAVE REPORTS
# ==========================================

robust_path = (
    REPORT_DIR / "robustness_scenarios.csv"
)

summary.to_csv(
    robust_path,
    index=False
)


# ==========================================
# 12. DISPLAY RESULTS
# ==========================================

print("\n--- EV CHARGING MONTE CARLO VALIDATION ---")

print(
    "Historical fast-category sessions:",
    len(valid)
)

print(
    "Simulated demand months:",
    REPETITIONS
)

print(
    "Days per simulation:",
    DAYS
)

print(
    "Mean cars per day:",
    MEAN_CARS_PER_DAY
)

print(
    "\n--- RELIABILITY RESULTS ---"
)

print(
    summary.to_string(index=False)
)

print(
    "\nReference dashboard report:",
    reference_path
)

print(
    "\nMonte Carlo reliability report:",
    robust_path
)

print(
    "\nSimulation completed successfully!"
)
