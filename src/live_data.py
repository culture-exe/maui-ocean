#!/usr/bin/env python3
"""
Live NOAA Buoy & Hawaii Environmental Telemetry Ingestion
Fetches live swell height, dominant period, trade winds, and precipitation for Maui / Hawaiian Coastlines.
Uses local file caching and background asynchronous polling to ensure zero audio glitching or blocking.
"""

import os
import sys
import time
import json
import urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta

CACHE_DIR = Path.home() / '.local/state/culture-ocean'
CACHE_FILE = CACHE_DIR / 'live_telemetry.json'
CACHE_TTL = 900  # 15 minutes

# Default climatological baseline for Maui (in case network is offline)
DEFAULT_TELEMETRY = {
    'timestamp': time.time(),
    'source': 'climatological_default',
    'location': 'Maui Coastal Waters',
    'wave_height_m': 1.6,
    'wave_period_s': 11.5,
    'wave_direction_deg': 75,
    'wind_speed_kmh': 18.0,
    'wind_direction_deg': 65,
    'precipitation_mm': 0.0,
    'temperature_c': 26.0,
    'weather_desc': 'Partly Cloudy Trade Wind Flow',
    'is_live': False
}

def get_hawaii_time():
    """Returns the current datetime in Hawaii Standard Time (HST, UTC-10)."""
    hst_tz = timezone(timedelta(hours=-10))
    return datetime.now(hst_tz)

def determine_circadian_phase(hst_dt=None):
    """
    Calculates Hawaiian circadian phase:
      - dawn (Kawaipuna / Kakahiaka): 05:30 - 08:30
      - day (Awakea / ʻAuina lā): 08:30 - 17:30
      - sunset (Nāulu / Ahiahi): 17:30 - 20:00
      - night (Pō): 20:00 - 05:30
    """
    if hst_dt is None:
        hst_dt = get_hawaii_time()
    
    hour = hst_dt.hour + hst_dt.minute / 60.0
    
    if 5.5 <= hour < 8.5:
        return 'dawn', 'Dawn (Kawaipuna / Kakahiaka)'
    elif 8.5 <= hour < 17.5:
        return 'day', 'Day / Afternoon (Awakea)'
    elif 17.5 <= hour < 20.0:
        return 'sunset', 'Sunset (Nāulu / Ahiahi)'
    else:
        return 'night', 'Night (Pō)'

def fetch_live_telemetry(force_refresh=False):
    """
    Fetches live marine swell and weather data from NOAA NDBC & Open-Meteo.
    Uses cached disk data if fresh. Falls back cleanly on network timeout.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if not force_refresh and CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text())
            age = time.time() - cached.get('timestamp', 0)
            if age < CACHE_TTL:
                return cached
        except Exception:
            pass

    telemetry = dict(DEFAULT_TELEMETRY)
    telemetry['timestamp'] = time.time()
    telemetry['hst_time'] = get_hawaii_time().strftime('%Y-%m-%d %H:%M:%S HST')
    phase, phase_name = determine_circadian_phase()
    telemetry['circadian_phase'] = phase
    telemetry['circadian_phase_name'] = phase_name

    # 1. Fetch NOAA Buoy 51205 (Pauwela, Maui North Shore) if possible
    buoy_success = False
    try:
        req = urllib.request.Request(
            'https://www.ndbc.noaa.gov/data/realtime2/51205.txt',
            headers={'User-Agent': 'CultureOcean/1.0'}
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            lines = resp.read().decode('utf-8', errors='ignore').splitlines()
            if len(lines) >= 3:
                cols = lines[2].split()
                # Cols: YY MM DD hh mm WDIR WSPD GST WVHT DPD APD MWD PRES ATMP WTMP
                if len(cols) >= 12:
                    wvht_str = cols[8]
                    dpd_str = cols[9]
                    if wvht_str != 'MM':
                        telemetry['wave_height_m'] = float(wvht_str)
                        buoy_success = True
                    if dpd_str != 'MM':
                        telemetry['wave_period_s'] = float(dpd_str)
                        buoy_success = True
                    telemetry['source'] = 'NOAA NDBC Buoy 51205 (Pauwela, Maui)'
    except Exception:
        pass

    # 2. Fetch Open-Meteo Maui Marine & Atmospheric Weather
    try:
        # Weather API (Wind, Precipitation, Temp)
        w_url = (
            'https://api.open-meteo.com/v1/forecast?'
            'latitude=20.7984&longitude=-156.3319&current='
            'temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,weather_code&timezone=Pacific%2FHonolulu'
        )
        req_w = urllib.request.Request(w_url, headers={'User-Agent': 'CultureOcean/1.0'})
        with urllib.request.urlopen(req_w, timeout=3.5) as resp:
            w_data = json.loads(resp.read().decode('utf-8'))
            cur = w_data.get('current', {})
            if cur:
                telemetry['wind_speed_kmh'] = float(cur.get('wind_speed_10m', 18.0))
                telemetry['wind_direction_deg'] = int(cur.get('wind_direction_10m', 65))
                telemetry['precipitation_mm'] = float(cur.get('precipitation', 0.0))
                telemetry['temperature_c'] = float(cur.get('temperature_2m', 25.0))
                telemetry['is_live'] = True
                if not buoy_success:
                    telemetry['source'] = 'Open-Meteo Maui Coastal Feed'
    except Exception:
        pass

    # If marine buoy wasn't available, check Open-Meteo Marine
    if not buoy_success:
        try:
            m_url = (
                'https://marine-api.open-meteo.com/v1/marine?'
                'latitude=20.90&longitude=-156.50&current='
                'wave_height,wave_period,wave_direction&timezone=Pacific%2FHonolulu'
            )
            req_m = urllib.request.Request(m_url, headers={'User-Agent': 'CultureOcean/1.0'})
            with urllib.request.urlopen(req_m, timeout=3.5) as resp:
                m_data = json.loads(resp.read().decode('utf-8'))
                m_cur = m_data.get('current', {})
                if m_cur:
                    telemetry['wave_height_m'] = float(m_cur.get('wave_height', 1.5))
                    telemetry['wave_period_s'] = float(m_cur.get('wave_period', 11.0))
                    telemetry['wave_direction_deg'] = int(m_cur.get('wave_direction', 80))
                    telemetry['is_live'] = True
                    telemetry['source'] = 'Open-Meteo Marine (Maui Channel)'
        except Exception:
            pass

    # Write cache
    try:
        CACHE_FILE.write_text(json.dumps(telemetry, indent=2))
    except Exception:
        pass

    return telemetry

def compute_dsp_multipliers(telemetry):
    """
    Translates physical ocean/weather telemetry into dynamic DSP scaling factors:
      - swell_gain_mult: swell power scaling based on wave height
      - wave_period_mult: wave timing based on dominant swell period
      - wind_gain_mult: trade wind noise scaling based on wind speed (km/h)
      - rain_intensity: 0.0 to 1.0 based on live precipitation
    """
    wvht = telemetry.get('wave_height_m', 1.5)
    period = telemetry.get('wave_period_s', 11.0)
    wind_kmh = telemetry.get('wind_speed_kmh', 18.0)
    precip_mm = telemetry.get('precipitation_mm', 0.0)

    # Wave height baseline ~ 1.5m
    swell_gain_mult = max(0.5, min(2.0, (wvht / 1.5) ** 0.65))
    
    # Wave period baseline ~ 11.0s
    wave_period_mult = max(0.65, min(1.6, period / 11.0))

    # Wind speed baseline ~ 18 km/h (~10 knots)
    wind_gain_mult = max(0.3, min(2.2, (wind_kmh / 18.0) ** 0.75))

    # Rain intensity (0.0 to 1.0)
    # 0.2 mm/h = light mist (0.2), 2.0 mm/h = moderate rain (0.6), >5.0 mm/h = heavy squall (1.0)
    rain_intensity = 0.0
    if precip_mm > 0.05:
        rain_intensity = min(1.0, 0.15 + (precip_mm / 4.0) * 0.85)

    return {
        'swell_gain_mult': swell_gain_mult,
        'wave_period_mult': wave_period_mult,
        'wind_gain_mult': wind_gain_mult,
        'rain_intensity': rain_intensity
    }

if __name__ == '__main__':
    t = fetch_live_telemetry(force_refresh=True)
    m = compute_dsp_multipliers(t)
    print("Telemetry:", json.dumps(t, indent=2))
    print("DSP Multipliers:", json.dumps(m, indent=2))
