
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

# Project paths
BASE_DIR = Path(__file__).resolve().parent

DATA_FILE = BASE_DIR / "data" / "hourly_session_arrivals.csv"

REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

# 1. Load historical data
df = pd.read_csv(DATA_FILE)

df["hour_start"] = pd.to_datetime(
    df["hour_start"], errors="coerce"
)

# Start with public-area charging locations
df = df[df["location_type"] == "public area"].copy()
df = df.dropna(subset=["hour_start"])

if df.empty:
    raise SystemExit("No public-area charging data found.")

# 2. Build continuous hourly timeline
# Missing hours are provisionally assumed to have zero arrivals
hourly = df.groupby("hour_start")["session_starts"].sum()

hours = pd.date_range(
    start=hourly.index.min(),
    end=hourly.index.max(),
    freq="h"
)

missing_hours = len(hours.difference(hourly.index))

df = hourly.reindex(hours, fill_value=0).reset_index()
df.columns = ["hour_start", "session_starts"]

# 3. Create calendar features
df["hour"] = df["hour_start"].dt.hour
df["day_of_week"] = df["hour_start"].dt.dayofweek
df["month"] = df["hour_start"].dt.month
df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

features = ["hour", "day_of_week", "month", "is_weekend"]

X = df[features]
y = df["session_starts"]

# 4. Chronological train/test split
# Train on earliest 80%, test on latest 20%
split = int(len(df) * 0.80)

if split < 168 or len(df) - split < 24:
    raise SystemExit("Insufficient data for evaluation.")

X_train = X.iloc[:split]
X_test = X.iloc[split:]

y_train = y.iloc[:split]
y_test = y.iloc[split:]

# 5. Historical seasonal baseline
# Average arrivals for each hour of the week
train_hour_of_week = (
    X_train["day_of_week"] * 24 + X_train["hour"]
)

test_hour_of_week = (
    X_test["day_of_week"] * 24 + X_test["hour"]
)

baseline_lookup = y_train.groupby(train_hour_of_week).mean()

baseline_predictions = (
    test_hour_of_week.map(baseline_lookup)
    .fillna(y_train.mean())
    .to_numpy()
)

baseline_mae = mean_absolute_error(
    y_test, baseline_predictions
)

# 6. Train machine learning model
model = RandomForestRegressor(
    n_estimators=120,
    min_samples_leaf=10,
    random_state=42,
    n_jobs=-1
)

model.fit(X_train, y_train)

# 7. Make predictions
predictions = np.maximum(
    0, model.predict(X_test)
)

# 8. Evaluate performance
model_mae = mean_absolute_error(y_test, predictions)

print("\n--- EV CHARGING FORECAST MODEL ---")
print("Location category: public area")
print("Training hours:", len(X_train))
print("Testing hours:", len(X_test))
print("Missing hours filled with zero:", missing_hours)

print("\n--- MODEL PERFORMANCE ---")
print(f"Seasonal baseline MAE: {baseline_mae:.3f}")
print(f"Random Forest MAE: {model_mae:.3f}")

if model_mae < baseline_mae:
    print("Result: ML model outperformed the baseline.")
else:
    print("Result: Baseline performed as well or better.")

# 9. Export results
results = pd.DataFrame({
    "hour_start": df["hour_start"].iloc[split:].values,
    "actual_sessions": y_test.values,
    "baseline_forecast": baseline_predictions,
    "ml_forecast": predictions
})

output_file = REPORT_DIR / "forecast_validation.csv"
results.to_csv(output_file, index=False)

print("\nForecast validation saved to:", output_file)
print("Model evaluation completed!")
