
import csv
from pathlib import Path

csv_path = Path(__file__).resolve().parent / "data" / "ChargingRecords.csv"

with open(csv_path, encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)

    print("CSV columns:")
    print(reader.fieldnames)

    print("\nFirst record:")
    print(next(reader, None))
