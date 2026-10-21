# cpcb_calculator.py
"""CPCB (Central Pollution Control Board) Air Quality Index (AQI) calculator.

Implements the Indian National AQI (INAQI) sub‑index calculation, enforces CPCB
rules (minimum pollutants, presence of PM2.5/PM10) and provides a safe,
clamped output for extreme concentrations.

Usage
-----
>>> from cpcb_calculator import calculate_aqi
>>> aqi, details = calculate_aqi({"pm2_5": 85, "pm10": 120, "no2": 70})
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Breakpoint tables (conc_low, conc_high, index_low, index_high)
# Units: µg/m³ for PM, ppb for gases, mg/m³ for CO (CPCB uses mg/m³).
# ---------------------------------------------------------------------------
PM25_BREAKPOINTS = [
    (0, 30, 0, 50),
    (31, 60, 51, 100),
    (61, 90, 101, 200),
    (91, 120, 201, 300),
    (121, 250, 301, 400),
    (251, 500, 401, 500),
]
PM10_BREAKPOINTS = [
    (0, 50, 0, 50),
    (51, 100, 51, 100),
    (101, 250, 101, 200),
    (251, 350, 201, 300),
    (351, 430, 301, 400),
    (431, 1000, 401, 500),
]
NO2_BREAKPOINTS = [
    (0, 40, 0, 50),
    (41, 80, 51, 100),
    (81, 180, 101, 200),
    (181, 280, 201, 300),
    (281, 400, 301, 400),
    (401, 1000, 401, 500),
]
SO2_BREAKPOINTS = [
    (0, 40, 0, 50),
    (41, 80, 51, 100),
    (81, 380, 101, 200),
    (381, 800, 201, 300),
    (801, 1600, 301, 400),
    (1601, 2620, 401, 500),
]
# CPCB lists CO in mg/m³ (8‑hr avg). AQICN supplies ppm; conversion factor ≈ 1.145 mg/m³ per ppm.
CO_BREAKPOINTS = [
    (0, 1, 0, 50),
    (1.1, 2, 51, 100),
    (2.1, 10, 101, 200),
    (10.1, 17, 201, 300),
    (17.1, 34, 301, 400),
    (34.1, 68, 401, 500),
]
O3_BREAKPOINTS = [
    (0, 50, 0, 50),
    (51, 100, 51, 100),
    (101, 168, 101, 200),
    (169, 208, 201, 300),
    (209, 748, 301, 400),
    (749, 1000, 401, 500),
]

BREAKPOINTS = {
    "pm2_5": PM25_BREAKPOINTS,
    "pm10": PM10_BREAKPOINTS,
    "no2": NO2_BREAKPOINTS,
    "so2": SO2_BREAKPOINTS,
    "co": CO_BREAKPOINTS,
    "o3": O3_BREAKPOINTS,
}

# CPCB AQI categories and associated colors
AQI_CATEGORIES = [
    (0, 50, "Good", "#009966"),
    (51, 100, "Satisfactory", "#70c1b3"),
    (101, 200, "Moderate", "#ffde33"),
    (201, 300, "Poor", "#ff9933"),
    (301, 400, "Very Poor", "#cc0033"),
    (401, 500, "Severe", "#660099"),
]

@dataclass
class SubIndexResult:
    pollutant: str
    concentration: float
    sub_index: int
    category: str
    color: str

def _calc_sub_index(conc: float, breakpoints: List[Tuple[float, float, int, int]]) -> int:
    """Return the CPCB sub‑index for a given concentration.

    The function safely clamps values outside the defined range to the nearest
    extreme index to avoid division‑by‑zero errors.
    """
    # Below lowest breakpoint – return the lowest index directly
    if conc < breakpoints[0][0]:
        return breakpoints[0][2]
    # Above highest breakpoint – return the highest index directly
    if conc > breakpoints[-1][1]:
        return breakpoints[-1][3]
    for B_lo, B_hi, I_lo, I_hi in breakpoints:
        if B_lo <= conc <= B_hi:
            # Linear interpolation as per CPCB formula
            return int(((I_hi - I_lo) / (B_hi - B_lo)) * (conc - B_lo) + I_lo)
    # Fallback (should never hit)
    return breakpoints[-1][3]

def _lookup_category(aqi: int) -> Tuple[str, str]:
    for lo, hi, name, color in AQI_CATEGORIES:
        if lo <= aqi <= hi:
            return name, color
    return "Severe", "#660099"

def _validate_input(conc_dict: Dict[str, float]) -> None:
    """Enforce CPCB minimum‑pollutant rule.

    - At least three pollutants must be supplied.
    - At least one of ``pm2_5`` or ``pm10`` must be present.
    """
    provided = [k for k in conc_dict if conc_dict[k] is not None]
    if len(provided) < 3:
        raise ValueError(
            "CPCB AQI requires concentrations for at least three pollutants."
        )
    if not ("pm2_5" in provided or "pm10" in provided):
        raise ValueError(
            "CPCB AQI must include either PM2.5 or PM10 concentration."
        )

def calculate_aqi(
    conc_dict: Dict[str, float], *, co_ppm_to_mg: bool = False
) -> Tuple[int, List[SubIndexResult]]:
    """Calculate the overall CPCB AQI from a dict of pollutant concentrations.

    Parameters
    ----------
    conc_dict:
        Mapping with keys ``pm2_5``, ``pm10``, ``no2``, ``so2``, ``co``, ``o3``.
    co_ppm_to_mg:
        If ``True`` the provided CO value (assumed ppm) is converted to mg/m³
        using the factor 1.145 before sub‑index calculation.
    """
    # Optional CO conversion (AQICN returns ppm for CO)
    if co_ppm_to_mg and "co" in conc_dict and conc_dict["co"] is not None:
        conc_dict["co"] = conc_dict["co"] * 1.145

    _validate_input(conc_dict)

    sub_results: List[SubIndexResult] = []
    for key, breakpoints in BREAKPOINTS.items():
        conc = conc_dict.get(key)
        if conc is None:
            continue
        sub_i = _calc_sub_index(conc, breakpoints)
        cat, col = _lookup_category(sub_i)
        sub_results.append(
            SubIndexResult(
                pollutant=key,
                concentration=conc,
                sub_index=sub_i,
                category=cat,
                color=col,
            )
        )
    overall_aqi = max(r.sub_index for r in sub_results)
    # Clamp overall AQI to the official maximum (500) for safety
    overall_aqi = min(max(overall_aqi, 0), 500)
    return overall_aqi, sub_results

if __name__ == "__main__":
    sample = {"pm2_5": 85, "pm10": 120, "no2": 70, "so2": 30, "co": 2.5, "o3": 80}
    aqi, details = calculate_aqi(sample, co_ppm_to_mg=False)
    print(f"Overall AQI: {aqi}")
    for d in details:
        print(f"{d.pollutant.upper():5}: {d.concentration} → {d.sub_index} ({d.category})")
