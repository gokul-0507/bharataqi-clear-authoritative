# VayuPulse — Real-Time Indian AQI Monitor & Predictor

Live Air Quality Index (AQI) monitoring and 24-hour prediction web application for Indian cities, built according to Central Pollution Control Board (CPCB) INAQI standards.

🌐 **Live Website:** [https://bharataqi-clear-authoritative-focus-on.onrender.com/](https://bharataqi-clear-authoritative-focus-on.onrender.com/)

---

## 📌 Features

- **Live CPCB INAQI Dashboard:** Real-time Indian National Air Quality Index calculation adhering to CPCB breakpoints for $\text{PM}_{2.5}$, $\text{PM}_{10}$, $\text{NO}_2$, $\text{SO}_2$, $\text{CO}$, and $\text{O}_3$.
- **Clean 2-Page Minimalist UX:**
  - **City Selection Hub:** Quick search and instant grid access across major Indian metropolitan hubs (Delhi, Mumbai, Bengaluru, Chennai, Kolkata, Hyderabad, Ahmedabad, Pune, Lucknow, Jaipur, etc.).
  - **AQI Hero & Forecast View:** High-visibility AQI numerical hero, official color-coded hazard category badge, dominant pollutant indicator, previous reading, and 24-hour prediction.
- **State Persistence & Routing:** Retains active city view on page reload using client-side routing.
- **High-Reliability Fallback:** Ensures continuous display even during upstream API latency or rate limits with calibrated realistic baselines.
- **Fully Responsive:** Mobile-first layout adapted seamlessly across phone (360px+), tablet, and desktop viewports.

---

## 🚀 Tech Stack

- **Frontend:** Vanilla HTML5, modern CSS3 (custom properties, fluid clamp typography, responsive grid), JavaScript (SPA routing & API integration).
- **Backend:** Python FastAPI, Uvicorn, HTTPX (async client), scikit-learn / joblib (predictive model).
- **Standards:** Official CPCB INAQI guidelines and category breakpoint interpolation.
- **Deployment:** Render / Docker.

---

## 🛠️ Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/gokul-0507/bharataqi-clear-authoritative.git
   cd bharataqi-clear-authoritative
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **(Optional) Set API Keys:**
   ```bash
   export AQICN_TOKEN="your_token_here"
   export OPENWEATHER_KEY="your_key_here"
   ```

4. **Start the local server:**
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```

5. Open [http://localhost:8000](http://localhost:8000) in your browser.
