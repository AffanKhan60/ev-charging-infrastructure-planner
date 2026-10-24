
import csv
import sqlite3
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "data" / "ChargingRecords.csv"
DB_FILE = BASE_DIR / "ev_charging.db"

# Check dataset exists
if not CSV_FILE.exists():
    raise SystemExit(f"CSV file not found: {CSV_FILE}")

# Connect to existing database
conn = sqlite3.connect(DB_FILE)

# Preserve existing database structure
conn.execute("""
CREATE TABLE IF NOT EXISTS charging_sessions (
    session_id TEXT PRIMARY KEY,
    charger_id TEXT NOT NULL,
    location_type TEXT,
    charger_type TEXT,
    start_time TEXT,
    duration_min REAL,
    energy_kwh REAL NOT NULL
)
""")

# Read actual CSV columns
records = []
skipped = 0

with open(CSV_FILE, encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)

    required = {
        "ChargerID", "Demand", "Duration",
        "Location", "ChargerType", "StartDatetime"
    }

    missing = required - set(reader.fieldnames or [])

    if missing:
        raise SystemExit(f"Missing CSV columns: {missing}")

    for row_number, row in enumerate(reader, start=1):
        try:
            charger_id = row["ChargerID"].strip()
            energy = float(row["Demand"])
            duration = float(row["Duration"])

            if not charger_id or energy < 0 or duration < 0:
                skipped += 1
                continue

            # Dataset has no unique charging-session ID
            session_id = f"SESSION-{row_number:06d}"

            records.append((
                session_id,
                charger_id,
                row["Location"],
                row["ChargerType"],
                row["StartDatetime"],
                duration,
                energy
            ))

        except (ValueError, TypeError, AttributeError):
            skipped += 1

if not records:
    conn.close()
    raise SystemExit("ERROR: No valid charging sessions found!")

# Import real sessions into SQLite
conn.executemany("""
INSERT OR REPLACE INTO charging_sessions
(session_id, charger_id, location_type,
 charger_type, start_time, duration_min, energy_kwh)
VALUES (?, ?, ?, ?, ?, ?, ?)
""", records)

conn.commit()

# Database statistics
stats = conn.execute("""
SELECT
    COUNT(*),
    COUNT(DISTINCT charger_id),
    ROUND(SUM(energy_kwh), 2)
FROM charging_sessions
""").fetchone()

print("\n--- REAL EV CHARGING DATA ---")
print("Charging sessions:", stats[0])
print("Unique chargers:", stats[1])
print("Total delivered energy:", stats[2], "kWh")
print("Invalid/skipped rows:", skipped)

# Analyze charging sessions by location
print("\n--- TOP 5 LOCATION TYPES ---")

locations = conn.execute("""
SELECT
    location_type,
    COUNT(*) AS sessions,
    ROUND(SUM(energy_kwh), 2) AS total_energy
FROM charging_sessions
GROUP BY location_type
ORDER BY sessions DESC
LIMIT 5
""").fetchall()

for location, sessions, energy in locations:
    print(f"{location}: {sessions} sessions, {energy} kWh")

conn.close()

print("\nReal charging data imported successfully!")
