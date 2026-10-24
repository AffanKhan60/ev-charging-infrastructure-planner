
import csv
from pathlib import Path

# Illustrative engineering assumptions
CONNECTORS = 8
POWER_PER_CONNECTOR_KW = 150

GRID_SCENARIOS_KW = [300, 600]
ACTIVE_VEHICLES = [1, 2, 4, 6, 8]

BASE_DIR = Path(__file__).resolve().parent
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

results = []

print("\n--- GRID POWER SHARING ANALYSIS ---")

for grid_power in GRID_SCENARIOS_KW:

    print(f"\nAvailable grid power: {grid_power} kW")

    for active in ACTIVE_VEHICLES:

        if active > CONNECTORS:
            continue

        # Maximum power each vehicle could receive
        power_per_ev = min(
            POWER_PER_CONNECTOR_KW,
            grid_power / active
        )

        # Total power delivered to all active vehicles
        total_power = power_per_ev * active

        # Remaining grid capacity
        unused_grid = grid_power - total_power

        print(
            f"{active} active EVs | "
            f"{power_per_ev:.1f} kW/EV | "
            f"Total: {total_power:.1f} kW"
        )

        results.append({
            "grid_capacity_kw": grid_power,
            "active_vehicles": active,
            "power_per_ev_kw": round(power_per_ev, 2),
            "total_power_kw": round(total_power, 2),
            "unused_grid_kw": round(unused_grid, 2)
        })

# Export the analysis
output_file = REPORT_DIR / "grid_power_sharing.csv"

with open(output_file, "w", newline="") as file:
    writer = csv.DictWriter(
        file, fieldnames=results[0].keys()
    )
    writer.writeheader()
    writer.writerows(results)

print("\nReport saved to:", output_file)
