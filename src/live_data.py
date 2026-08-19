#!/usr/bin/env python3
"""
Live NOAA Buoy & Hawaii Environmental Telemetry Ingestion
Fetches live swell height, dominant period, trade winds, and precipitation
for Hawaiian Coastlines. Uses a background daemon thread for asynchronous
polling to ensure zero audio glitching or blocking on the DSP thread.

Supports per-island buoy IDs and coordinates for Maui and Kauaʻi.
"""

import os
import sys
import time
import json
import logging
import threading
import urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("culture-ocean.live_data")

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

# --- Island / buoy registry ---
ISLAND_CONFIG = {
    'Maui': {
        'latitude': 20.7984,
        'longitude': -156.3319,
        'buoy_id': '51205',
        'buoy_name': 'Pauwela, Maui North Shore',
    },
    "Kauaʻi": {
        'latitude': 22.22,
        'longitude': -159.55,
        'buoy_id': '51201',   # Waimea Bay, Kauaʻi (NDBC 51201)
        'buoy_name': 'Waimea Bay, Kauaʻi',
    },
    'Hawaii': {  # fallback / generic
        'latitude': 20.7984,
        'longitude': -156.3319,
        'buoy_id': '51205',
        'buoy_name': 'Pauwela, Maui',
    }
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


# ---------------------------------------------------------------------------
# Robust NOAA NDBC realtime2 parser
# ---------------------------------------------------------------------------

def _parse_ndbc_realtime2(text):
    """
    Parse NOAA NDBC realtime2 fixed-width/text table.
    Returns dict of {column_name: value} for the most recent complete data row.
    Returns None on parse failure.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith('#')]
    if len(lines) < 3:
        return None

    # NDBC format: line 0 = column headers, line 1 = units, lines[2:] = data
    headers = lines[0].split()
    if len(headers) < 5:
        return None

    # Walk backward to find the first line with enough numeric-looking fields
    data_line = None
    for line in reversed(lines[2:]):
        cols = line.split()
        if len(cols) >= len(headers) - 1:  # allow for missing trailing columns
            data_line = cols
            break
    if data_line is None:
        return None

    result = {}
    for i, hdr in enumerate(headers):
        if i < len(data_line):
            val = data_line[i]
            if val not in ('MM', '99', '999', '9999', '99.0', '999.0'):
                try:
                    result[hdr] = float(val)
                except ValueError:
                    pass
    return result


# ---------------------------------------------------------------------------
# Telemetry fetching (called from background thread)
# ---------------------------------------------------------------------------

def _fetch_noaa_buoy(buoy_id, telemetry):
    """Fetch from a single NOAA NDBC buoy.  Mutates telemetry dict in place."""
    try:
        url = f'https://www.ndbc.noaa.gov/data/realtime2/{buoy_id}.txt'
        req = urllib.request.Request(url, headers={'User-Agent': 'CultureOcean/1.1'})
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            raw = resp.read().decode('utf-8', errors='ignore')
        parsed = _parse_ndbc_realtime2(raw)
        if parsed:
            if 'WVHT' in parsed:
                telemetry['wave_height_m'] = parsed['WVHT']
            if 'DPD' in parsed:
                telemetry['wave_period_s'] = parsed['DPD']
            if 'WDIR' in parsed:
                telemetry['wind_direction_deg'] = int(parsed['WDIR'])
            if 'WSPD' in parsed:
                telemetry['wind_speed_kmh'] = parsed['WSPD'] * 1.852  # knots → km/h
            telemetry['source'] = f'NOAA NDBC Buoy {buoy_id}'
            telemetry['is_live'] = True
            telemetry['buoy_success'] = True
            return True
    except Exception:
        logger.debug("NOAA buoy %s fetch failed", buoy_id, exc_info=True)
    return False


def _fetch_open_meteo_weather(lat, lon, telemetry):
    """Fetch Open-Meteo atmospheric weather.  Mutates telemetry dict."""
    try:
        w_url = (
            'https://api.open-meteo.com/v1/forecast?'
            f'latitude={lat}&longitude={lon}&current='
            'temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,weather_code'
            '&timezone=Pacific%2FHonolulu'
        )
        req = urllib.request.Request(w_url, headers={'User-Agent': 'CultureOcean/1.1'})
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            w_data = json.loads(resp.read().decode('utf-8'))
        cur = w_data.get('current', {})
        if cur:
            telemetry['wind_speed_kmh'] = float(cur.get('wind_speed_10m', telemetry.get('wind_speed_kmh', 18.0)))
            telemetry['wind_direction_deg'] = int(cur.get('wind_direction_10m', telemetry.get('wind_direction_deg', 65)))
            telemetry['precipitation_mm'] = float(cur.get('precipitation', 0.0))
            telemetry['temperature_c'] = float(cur.get('temperature_2m', telemetry.get('temperature_c', 25.0)))
            telemetry['is_live'] = True
            if not telemetry.get('buoy_success'):
                telemetry['source'] = 'Open-Meteo Weather Feed'
    except Exception:
        logger.debug("Open-Meteo weather fetch failed", exc_info=True)


def _fetch_open_meteo_marine(lat, lon, telemetry):
    """Fetch Open-Meteo marine wave data.  Mutates telemetry dict."""
    try:
        m_url = (
            'https://marine-api.open-meteo.com/v1/marine?'
            f'latitude={lat}&longitude={lon}&current='
            'wave_height,wave_period,wave_direction&timezone=Pacific%2FHonolulu'
        )
        req = urllib.request.Request(m_url, headers={'User-Agent': 'CultureOcean/1.1'})
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            m_data = json.loads(resp.read().decode('utf-8'))
        m_cur = m_data.get('current', {})
        if m_cur:
            if not telemetry.get('buoy_success'):
                telemetry['wave_height_m'] = float(m_cur.get('wave_height', telemetry.get('wave_height_m', 1.5)))
                telemetry['wave_period_s'] = float(m_cur.get('wave_period', telemetry.get('wave_period_s', 11.0)))
                telemetry['wave_direction_deg'] = int(m_cur.get('wave_direction', telemetry.get('wave_direction_deg', 80)))
            telemetry['is_live'] = True
            if not telemetry.get('buoy_success') and 'Open-Meteo' not in telemetry.get('source', ''):
                telemetry['source'] = 'Open-Meteo Marine Feed'
    except Exception:
        logger.debug("Open-Meteo marine fetch failed", exc_info=True)


def fetch_live_telemetry(force_refresh=False, latitude=None, longitude=None, buoy_id=None):
    """
    Fetches live marine swell and weather data from NOAA NDBC & Open-Meteo.
    Uses cached disk data if fresh.  Falls back cleanly on network timeout.

    Parameters
    ----------
    force_refresh : bool
        If True, skip the disk cache.
    latitude, longitude : float or None
        Coordinates for Open-Meteo queries (defaults to Maui).
    buoy_id : str or None
        NOAA NDBC buoy ID (defaults to 51205 – Pauwela, Maui).
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if not force_refresh and CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text())
            age = time.time() - cached.get('timestamp', 0)
            if age < CACHE_TTL:
                return cached
        except Exception:
            logger.debug("Telemetry cache read failed, will re-fetch", exc_info=True)

    if latitude is None:
        latitude = 20.7984
    if longitude is None:
        longitude = -156.3319
    if buoy_id is None:
        buoy_id = '51205'

    telemetry = dict(DEFAULT_TELEMETRY)
    telemetry['timestamp'] = time.time()
    telemetry['hst_time'] = get_hawaii_time().strftime('%Y-%m-%d %H:%M:%S HST')
    phase, phase_name = determine_circadian_phase()
    telemetry['circadian_phase'] = phase
    telemetry['circadian_phase_name'] = phase_name
    telemetry['buoy_success'] = False

    # 1. Fetch NOAA Buoy
    _fetch_noaa_buoy(buoy_id, telemetry)

    # 2. Fetch Open-Meteo atmospheric weather
    _fetch_open_meteo_weather(latitude, longitude, telemetry)

    # 3. If buoy didn't succeed, try Open-Meteo marine
    if not telemetry.get('buoy_success'):
        _fetch_open_meteo_marine(latitude, longitude, telemetry)

    # Write cache
    try:
        CACHE_FILE.write_text(json.dumps(telemetry, indent=2))
    except Exception:
        logger.debug("Failed to write telemetry cache", exc_info=True)

    return telemetry


# ---------------------------------------------------------------------------
# DSP multiplier computation
# ---------------------------------------------------------------------------

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

    swell_gain_mult = max(0.5, min(2.0, (wvht / 1.5) ** 0.65))
    wave_period_mult = max(0.65, min(1.6, period / 11.0))
    wind_gain_mult = max(0.3, min(2.2, (wind_kmh / 18.0) ** 0.75))

    rain_intensity = 0.0
    if precip_mm > 0.05:
        rain_intensity = min(1.0, 0.15 + (precip_mm / 4.0) * 0.85)

    return {
        'swell_gain_mult': swell_gain_mult,
        'wave_period_mult': wave_period_mult,
        'wind_gain_mult': wind_gain_mult,
        'rain_intensity': rain_intensity
    }


# ---------------------------------------------------------------------------
# Background Telemetry Manager (thread-safe, non-blocking)
# ---------------------------------------------------------------------------

class TelemetryManager:
    """
    Singleton-style background telemetry fetcher.
    Runs a daemon thread that periodically fetches live data.
    The audio thread calls get_multipliers() which never blocks.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._telemetry = dict(DEFAULT_TELEMETRY)
        self._multipliers = {
            'swell_gain_mult': 1.0,
            'wave_period_mult': 1.0,
            'wind_gain_mult': 1.0,
            'rain_intensity': 0.0,
        }
        self._latitude = 20.7984
        self._longitude = -156.3319
        self._buoy_id = '51205'
        self._running = False
        self._thread = None
        self._refresh_interval = 600.0  # 10 minutes

    def configure(self, *, latitude=None, longitude=None, buoy_id=None, island=None):
        """Set the geographic target for telemetry fetches."""
        if island and island in ISLAND_CONFIG:
            cfg = ISLAND_CONFIG[island]
            self._latitude = cfg['latitude']
            self._longitude = cfg['longitude']
            self._buoy_id = cfg['buoy_id']
        if latitude is not None:
            self._latitude = latitude
        if longitude is not None:
            self._longitude = longitude
        if buoy_id is not None:
            self._buoy_id = buoy_id

    def start(self):
        """Start the background telemetry thread (idempotent)."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="telemetry-fetcher")
        self._thread.start()
        logger.info("Telemetry background thread started (buoy=%s, lat=%.2f, lon=%.2f)",
                     self._buoy_id, self._latitude, self._longitude)

    def stop(self):
        """Signal the background thread to stop."""
        self._running = False

    def _run(self):
        """Background loop: fetch telemetry, update multipliers, sleep."""
        while self._running:
            try:
                t = fetch_live_telemetry(
                    force_refresh=True,
                    latitude=self._latitude,
                    longitude=self._longitude,
                    buoy_id=self._buoy_id,
                )
                mults = compute_dsp_multipliers(t)
                with self._lock:
                    self._telemetry = t
                    self._multipliers = mults
                logger.debug("Telemetry refreshed: swell=%.2fm, period=%.1fs, wind=%.1fkm/h, rain=%.2f",
                             t.get('wave_height_m', 0), t.get('wave_period_s', 0),
                             t.get('wind_speed_kmh', 0), mults.get('rain_intensity', 0))
            except Exception:
                logger.warning("Telemetry background fetch failed", exc_info=True)

            # Sleep in small increments so we can respond to stop() quickly
            for _ in range(int(self._refresh_interval)):
                if not self._running:
                    break
                time.sleep(1.0)

    def get_multipliers(self):
        """Return the latest DSP multipliers (non-blocking)."""
        with self._lock:
            return dict(self._multipliers)

    def get_telemetry(self):
        """Return the latest telemetry dict (non-blocking)."""
        with self._lock:
            return dict(self._telemetry)

    def get_circadian_phase(self):
        """Return (phase_code, phase_name) for current HST time."""
        return determine_circadian_phase()


# Module-level singleton (created lazily by HawaiianOceanSynthesizer)
_telemetry_manager = None


def get_telemetry_manager():
    """Return (or create) the module-level TelemetryManager singleton."""
    global _telemetry_manager
    if _telemetry_manager is None:
        _telemetry_manager = TelemetryManager()
    return _telemetry_manager


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    mgr = get_telemetry_manager()
    mgr.configure(island='Maui')
    mgr.start()
    time.sleep(2)
    t = mgr.get_telemetry()
    m = mgr.get_multipliers()
    print("Telemetry:", json.dumps(t, indent=2))
    print("Multipliers:", json.dumps(m, indent=2))
    mgr.stop()
