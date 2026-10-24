
import sqlite3
from pathlib import Path

# Database will be stored in our project folder
DB_PATH = Path(__file__).resolve().parent / "ev_charging.db"

# Illustrative hourly energy demand (kWh)
# Represents requested energy, not necessarily delivered energy
hourly_demand = [
    40, 30, 25, 20, 20, 30,
    50, 80, 110, 140, 160, 170,
    160, 150, 150, 250, 270, 310,
    360, 250, 170, 120, 80, 55
]

# Connect to SQLite
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")
cursor = conn.cursor()

# Create site table
cursor.execute("""
CREATE TABLE IF NOT EXISTS charging_sites (
    site_id TEXT PRIMARY KEY,
    grid_limit_kw REAL NOT NULL
)
""")

# Create hourly demand table
cursor.execute("""
CREATE TABLE IF NOT EXISTS hourly_demand (
    site_id TEXT NOT NULL,
    hour INTEGER NOT NULL CHECK(hour BETWEEN 0 AND 23),
    requested_energy_kwh REAL NOT NULL CHECK(requested_energy_kwh >= 0),
    PRIMARY KEY (site_id, hour),
    FOREIGN KEY (site_id) REFERENCES charging_sites(site_id)
)
""")

# Save site configuration
cursor.execute("""
INSERT OR REPLACE INTO charging_sites
(site_id, grid_limit_kw)
VALUES (?, ?)
""", ("DE-001", 300))

# Save hourly demand
for hour, energy in enumerate(hourly_demand):
    cursor.execute("""
    INSERT OR REPLACE INTO hourly_demand
    (site_id, hour, requested_energy_kwh)
    VALUES (?, ?, ?)
    """, ("DE-001", hour, energy))

conn.commit()

# SQL Query 1: Total daily demand
cursor.execute("""
SELECT SUM(requested_energy_kwh)
FROM hourly_demand
WHERE site_id = ?
""", ("DE-001",))

total = cursor.fetchone()[0]

# SQL Query 2: Find hours exceeding the grid limit
# One row = one hour, so energy in kWh / 1h = average kW
cursor.execute("""
SELECT h.hour,
       h.requested_energy_kwh,
       s.grid_limit_kw
FROM hourly_demand AS h
JOIN charging_sites AS s
    ON h.site_id = s.site_id
WHERE h.site_id = ?
  AND h.requested_energy_kwh > s.grid_limit_kw
ORDER BY h.hour
""", ("DE-001",))

overloaded_hours = cursor.fetchall()

print("\n--- EV CHARGING DATABASE ---")
print("Database:", DB_PATH.name)
print("Total daily demand:", total, "kWh")

print("\n--- GRID CAPACITY ANALYSIS ---")
for hour, energy, grid_limit in overloaded_hours:
    excess = energy - grid_limit
    print(f"{hour:02d}:00 - Excess demand: {excess:.1f} kWh")

print("\nDatabase created successfully!")

conn.close()
