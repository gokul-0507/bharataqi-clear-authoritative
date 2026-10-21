# app.py
"""
FastAPI backend for the CPCB Air Quality Index predictor & dashboard.
Provides:
  - /api/aqi/current  → live pollutant data + CPCB AQI calculation
  - /api/aqi/predict  → 24-h AQI forecast (ML model or static fallback)
  - /api/aqi/advice   → health advice text per CPCB category
  - /                 → serves index.html (SPA)
  - /static/*         → static assets

Robustness features:
  - Exponential-backoff retry for external API calls
  - In-memory cache of last successful payload per city
  - Input validation (city name regex)
  - CO ppm→mg/m³ conversion before CPCB calculation
  - CORS middleware (open for dev; restrict in prod)
  - ML model output clipped to 0-500
"""

import os
import re
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import httpx
import joblib
import pandas as pd

from cpcb_calculator import calculate_aqi, AQI_CATEGORIES

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("aqi-backend")

# ---------------------------------------------------------------------------
# App & middleware
# ---------------------------------------------------------------------------
app = FastAPI(title="CPCB AQI Predictor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Optional ML model
# ---------------------------------------------------------------------------
_MODEL_PATH = Path(__file__).with_name("aqi_model.pkl")
model = joblib.load(_MODEL_PATH) if _MODEL_PATH.exists() else None
if model is None:
    logger.warning("aqi_model.pkl not found – /api/aqi/predict will return 503.")

# ---------------------------------------------------------------------------
# API keys (environment variables)
# ---------------------------------------------------------------------------
AQICN_TOKEN    = os.getenv("AQICN_TOKEN")
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY")

# ---------------------------------------------------------------------------
# In-memory cache (last good payload per city)
# ---------------------------------------------------------------------------
_cache: Dict[str, Dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# City-name validation
# ---------------------------------------------------------------------------
_CITY_RE = re.compile(r"^[a-zA-Z\s\-]{2,60}$")

def _validate_city(city: str) -> str:
    city = city.strip()
    if not _CITY_RE.fullmatch(city):
        raise HTTPException(status_code=400, detail="Invalid city name.")
    return city

# ---------------------------------------------------------------------------
# Async retry helper
# ---------------------------------------------------------------------------
async def _retry(fn, *args, retries: int = 3, backoff: float = 0.5, **kwargs):
    for attempt in range(1, retries + 2):
        try:
            return await fn(*args, **kwargs)
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            if attempt > retries:
                raise
            wait = backoff * (2 ** (attempt - 1))
            logger.warning(f"Retry {attempt}/{retries} for {fn.__name__} in {wait}s: {exc}")
            await asyncio.sleep(wait)

# ---------------------------------------------------------------------------
# External data fetchers
# ---------------------------------------------------------------------------
async def _fetch_aqicn(city: str) -> Dict[str, Any]:
    if not AQICN_TOKEN:
        raise HTTPException(status_code=500, detail="AQICN_TOKEN env variable not set.")
    url = f"https://api.waqi.info/feed/{city}/?token={AQICN_TOKEN}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
    data = resp.json()
    if data.get("status") != "ok":
        raise HTTPException(status_code=404, detail=f"No data for city: {city}")
    iaqi = data["data"].get("iaqi", {})
    mapping = {"pm25": "pm2_5", "pm10": "pm10", "no2": "no2", "so2": "so2", "co": "co", "o3": "o3"}
    result: Dict[str, Any] = {}
    for api_key, internal in mapping.items():
        v = iaqi.get(api_key)
        if v:
            result[internal] = float(v["v"] if isinstance(v, dict) else v)
    geo = data["data"].get("city", {}).get("geo", [])
    if len(geo) == 2:
        result["lat"], result["lon"] = geo[0], geo[1]
    result["timestamp"] = data["data"].get("time", {}).get("s")
    return result


async def _fetch_weather(lat: float, lon: float) -> Dict[str, Any]:
    if not OPENWEATHER_KEY:
        return {"temperature": None, "humidity": None}
    url = (
        f"https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}"
        f"&exclude=minutely,daily,alerts&units=metric&appid={OPENWEATHER_KEY}"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
    cur = resp.json().get("current", {})
    return {"temperature": cur.get("temp"), "humidity": cur.get("humidity")}

# ---------------------------------------------------------------------------
# Health advice text
# ---------------------------------------------------------------------------
_ADVICE = {
    "Good":        "Air quality is satisfactory; air pollution poses little or no risk.",
    "Satisfactory":"Air quality is acceptable; some pollutants may irritate very sensitive individuals.",
    "Moderate":    "Sensitive groups (children, elderly, asthma sufferers) may experience health effects.",
    "Poor":        "People with respiratory or heart disease, the elderly, and children should limit prolonged outdoor exertion.",
    "Very Poor":   "Everyone may experience more serious health effects; avoid outdoor activities.",
    "Severe":      "Health emergency. The entire population is likely to be affected. Stay indoors.",
}

def _category_from_aqi(aqi: int) -> tuple:
    for lo, hi, name, color in AQI_CATEGORIES:
        if lo <= aqi <= hi:
            return name, color
    return "Severe", "#660099"

# ---------------------------------------------------------------------------
# Endpoint: current AQI
# ---------------------------------------------------------------------------
@app.get("/api/aqi/current")
async def get_current_aqi(city: str = Query(..., description="Indian city name")):
    city = _validate_city(city)
    try:
        raw = await _retry(_fetch_aqicn, city)
    except HTTPException:
        cached = _cache.get(city.lower())
        if cached:
            logger.info(f"Serving cached data for {city}")
            raw = cached
        else:
            raise
    _cache[city.lower()] = raw

    lat, lon = raw.get("lat"), raw.get("lon")
    weather = {"temperature": None, "humidity": None}
    if lat is not None and lon is not None:
        try:
            weather = await _retry(_fetch_weather, lat, lon)
        except Exception:
            pass

    calc_input = {k: v for k, v in raw.items()
                  if k in {"pm2_5", "pm10", "no2", "so2", "co", "o3"} and v is not None}
    try:
        overall_aqi, details = calculate_aqi(calc_input, co_ppm_to_mg=True)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    return JSONResponse({
        "city":      city,
        "aqi":       overall_aqi,
        "details":   [d.__dict__ for d in details],
        "timestamp": raw.get("timestamp"),
        "weather":   weather,
    })

# ---------------------------------------------------------------------------
# Endpoint: 24-hour prediction
# ---------------------------------------------------------------------------
@app.get("/api/aqi/predict")
async def predict_aqi(city: str = Query(..., description="Indian city name")):
    if model is None:
        raise HTTPException(status_code=503, detail="Prediction model unavailable (aqi_model.pkl missing).")
    city = _validate_city(city)

    # Ensure we have a cached observation
    await get_current_aqi(city)
    latest = _cache.get(city.lower(), {})

    pollutants   = ["pm2_5", "pm10", "no2", "so2", "co", "o3"]
    weather_vars = ["temperature", "humidity"]
    lag_features: Dict[str, Any] = {}
    for col in pollutants + weather_vars:
        val = latest.get(col) or 0.0
        for lag in range(1, 25):
            lag_features[f"{col}_lag_{lag}"] = val

    pred = model.predict(pd.DataFrame([lag_features]))[0]
    pred = float(min(max(pred, 0), 500))
    return JSONResponse({"city": city, "predicted_aqi": round(pred, 2)})

# ---------------------------------------------------------------------------
# Endpoint: health advice
# ---------------------------------------------------------------------------
@app.get("/api/aqi/advice")
async def get_advice(city: str = Query(...)):
    resp = await get_current_aqi(city)
    aqi_val = resp.body  # JSONResponse .body is bytes; decode
    import json
    body = json.loads(resp.body)
    aqi_val = body["aqi"]
    cat, _ = _category_from_aqi(aqi_val)
    return JSONResponse({"city": city, "aqi": aqi_val, "category": cat, "advice": _ADVICE.get(cat, "Stay safe.")})

# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR, html=True), name="static")

@app.get("/", response_class=FileResponse)
async def root():
    return FileResponse(BASE_DIR / "index.html")
