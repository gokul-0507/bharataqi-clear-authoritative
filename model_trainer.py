# model_trainer.py
"""
Training script for 24‑hour AQI forecasting.
It uses historical pollutant concentrations and weather variables to predict the next day's average AQI.
The resulting model (scikit‑learn pipeline) is saved as `aqi_model.pkl` for serving via FastAPI.
"""

import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib

# ---------------------------------------------------------------------------
# Helper: generate lag features (previous 24‑hour values) for each variable
# ---------------------------------------------------------------------------
def create_lag_features(df: pd.DataFrame, columns: list, lags: int = 24) -> pd.DataFrame:
    """Add lagged versions of ``columns`` up to ``lags`` hours.
    Assumes ``df`` is indexed by a datetime hourly frequency.
    """
    for col in columns:
        for lag in range(1, lags + 1):
            df[f"{col}_lag_{lag}"] = df[col].shift(lag)
    df = df.dropna().reset_index(drop=True)
    return df

# ---------------------------------------------------------------------------
# Load historical data (placeholder – replace with actual CSV/DB source)
# ---------------------------------------------------------------------------
DATA_PATH = os.path.join(os.path.dirname(__file__), "historical_aqi.csv")
if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(f"Historical data file not found: {DATA_PATH}")

# Expected columns: datetime, pm2_5, pm10, no2, so2, co, o3, temperature, humidity, aqi
raw = pd.read_csv(DATA_PATH, parse_dates=["datetime"])
raw = raw.sort_values("datetime")
raw = raw.set_index("datetime")

# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------
pollutants = ["pm2_5", "pm10", "no2", "so2", "co", "o3"]
weather = ["temperature", "humidity"]
feature_cols = pollutants + weather

# Create lag features for the previous 24 hours
feature_df = create_lag_features(raw[feature_cols + ["aqi"]].copy(), feature_cols, lags=24)

X = feature_df.drop(columns=["aqi"])
# Target is the AQI 24 hours ahead (i.e., the current row's AQI after lagging)
y = feature_df["aqi"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, shuffle=False
)

pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("rf", RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)),
])

pipeline.fit(X_train, y_train)

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
preds = pipeline.predict(X_test)
print("Evaluation metrics for 24‑hr AQI forecast:")
print(f"R^2   : {r2_score(y_test, preds):.4f}")
print(f"MAE   : {mean_absolute_error(y_test, preds):.2f}")
print(f"RMSE  : {np.sqrt(mean_squared_error(y_test, preds)):.2f}")

# ---------------------------------------------------------------------------
# Save model for serving
# ---------------------------------------------------------------------------
MODEL_PATH = os.path.join(os.path.dirname(__file__), "aqi_model.pkl")
joblib.dump(pipeline, MODEL_PATH)
print(f"Model saved to {MODEL_PATH}")
