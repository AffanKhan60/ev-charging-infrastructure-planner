
# EV Charging Site Planner - Version 0.1

# Charging site specifications
chargers = 4
charger_power_kw = 150
hours_per_day = 24

# Average effective utilization (20%)
utilization = 0.20

# Expected daily energy demand
daily_demand_kwh = 3200

# YOUR TASK:
# Calculate the daily energy capacity of the site

daily_capacity_kwh =  chargers * charger_power_kw * hours_per_day * utilization

print("Daily capacity:", daily_capacity_kwh, "kWh")
print("Daily demand:", daily_demand_kwh, "kWh")

if daily_capacity_kwh >= daily_demand_kwh:
    print("Site capacity is sufficient.")

else:
    energy_shortage = daily_demand_kwh - daily_capacity_kwh
    print("Site capacity is insufficient.")
    print("Energy shortage:", energy_shortage, "kWh")


import math

# Calculate energy capacity of one charger
energy_per_charger = charger_power_kw * hours_per_day * utilization

# Calculate the number of chargers required
required_chargers = math.ceil(daily_demand_kwh / energy_per_charger)

# Calculate how many additional chargers are needed
additional_chargers = max(0, required_chargers - chargers)

print("Required chargers:", required_chargers)
print("Additional chargers needed:", additional_chargers)


# Hourly energy demand (kWh)
# Index 0 = 00:00-01:00, index 18 = 18:00-19:00


# Hourly charging demand analysis

hourly_demand = [
    40, 30, 25, 20, 20, 30,
    50, 80, 110, 140, 160, 170,
    160, 150, 150, 250, 270, 310,
    360, 250, 170, 120, 80, 55
]

grid_capacity_kw = 300

# Calculate total daily demand
total_demand = sum(hourly_demand)

# Find peak hourly energy demand
peak_demand = max(hourly_demand)

# Find the hour with highest demand
peak_hour = hourly_demand.index(peak_demand)

# Identify hours exceeding grid capacity
# Each entry represents energy demand over one hour
print("\n--- HOURLY DEMAND ANALYSIS ---")
print("Total daily demand:", total_demand, "kWh")
print("Peak hourly demand:", peak_demand, "kWh")
print("Peak hour:", peak_hour, ":00")

print("\n--- GRID CAPACITY CHECK ---")

for hour, demand in enumerate(hourly_demand):
    if demand > grid_capacity_kw:
        shortage = demand - grid_capacity_kw
        print(f"Hour {hour}:00 - Grid limit exceeded by {shortage} kWh")
