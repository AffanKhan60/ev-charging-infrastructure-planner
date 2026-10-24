
import sqlite3
import csv
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "ev_charging.db"

REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

# Connect to database
conn = sqlite3.connect(DB_FILE)

# SQL analysis by charging location type
query = """
SELECT
    COALESCE(NULLIF(TRIM(location_type), ''), 'unknown')
        AS location_type,

    COUNT(*) AS total_sessions,

    COUNT(DISTINCT charger_id) AS total_chargers,

    ROUND(SUM(energy_kwh), 2) AS total_energy_kwh,

    ROUND(AVG(energy_kwh), 2) AS avg_energy_per_session,

    ROUND(
        CAST(COUNT(*) AS REAL)
        / COUNT(DISTINCT charger_id), 2
    ) AS sessions_per_charger

FROM charging_sessions

GROUP BY
    COALESCE(NULLIF(TRIM(location_type), ''), 'unknown')

ORDER BY total_sessions DESC
"""

cursor = conn.execute(query)

columns = [description[0] for description in cursor.description]
results = cursor.fetchall()

if not results:
    conn.close()
    raise SystemExit("No charging records found in database.")

# Save analysis as CSV
output_file = REPORT_DIR / "location_analysis.csv"

with open(output_file, "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(columns)
    writer.writerows(results)

# Display results
print("\n--- EV CHARGING LOCATION ANALYSIS ---")

for row in results:
    location, sessions, chargers, energy, avg, per_charger = row

    print(f"\nLocation: {location}")
    print(f"  Sessions: {sessions}")
    print(f"  Chargers: {chargers}")
    print(f"  Total energy: {energy} kWh")
    print(f"  Average session energy: {avg} kWh")
    print(f"  Sessions per charger: {per_charger}")

conn.close()

print("\nReport saved to:", output_file)
print("Analysis completed successfully!")
