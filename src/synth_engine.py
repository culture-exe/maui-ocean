#!/usr/bin/env python3
"""
Hawaiian Ocean Beach Generative Acoustic Synthesizer
Fully procedural, real-time DSP physical-acoustic model of Maui and Kauaʻi coastlines.
Includes live NOAA/Open-Meteo telemetry coupling (background thread, non-blocking),
24-hour diurnal circadian transitions, tropical rain generators, black sand/volcanic
pebble acoustics, blowholes, hollow barrels, and nocturnal coastal crickets.
"""

import time
import random
import logging
import numpy as np
from scipy import signal

from .live_data import (
    get_telemetry_manager,
    determine_circadian_phase,
)

logger = logging.getLogger("culture-ocean.synth")

SAMPLE_RATE = 48000


class FastPinkNoise:
    """Vectorized 3-pole IIR filter for pink noise generation (constant state)."""
    def __init__(self, channels=2):
        self.channels = channels
        self.b = np.array([0.049922035, -0.095993537, 0.050612699, -0.004408786])
        self.a = np.array([1.0, -2.494956002, 2.017265875, -0.522189400])
        self.zi = np.zeros((max(len(self.a), len(self.b)) - 1, channels))

    def generate(self, n):
        white = np.random.normal(0, 1.0, (n, self.channels))
        out, self.zi = signal.lfilter(self.b, self.a, white, axis=0, zi=self.zi)
        return out * 1.6


class FastBrownNoise:
    """Vectorized leaky integrator for sub-bass deep ocean foundation."""
    def __init__(self, channels=2, leak=0.995):
        self.channels = channels
        self.b = np.array([1.0 - leak])
        self.a = np.array([1.0, -leak])
        self.zi = np.zeros((1, channels))

    def generate(self, n):
        white = np.random.normal(0, 1.0, (n, self.channels))
        out, self.zi = signal.lfilter(self.b, self.a, white, axis=0, zi=self.zi)
        return out * 5.5


class RainGenerator:
    """
    Procedural Tropical Squall & Rain-on-Ocean DSP.
    Synthesizes stochastic Poisson raindrop impacts, high-frequency water
    surface sizzle, and distant rolling Pacific thunder rumbles.
    """
    def __init__(self, sample_rate=SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.intensity = 0.0       # 0.0 (dry) to 1.0 (heavy tropical squall)
        self.current_gain = 0.0

        # High-pass filter for crisp raindrop spray (2.4 kHz)
        self.sos_rain_spray = signal.butter(2, 2400.0, btype='highpass',
                                            fs=self.sample_rate, output='sos')
        self.zi_spray = np.zeros((self.sos_rain_spray.shape[0], 2, 2))

        # Bandpass filter for droplet water surface impacts (3.2–8.5 kHz)
        self.sos_droplets = signal.butter(2, [3200.0, 8500.0], btype='bandpass',
                                          fs=self.sample_rate, output='sos')
        self.zi_droplets = np.zeros((self.sos_droplets.shape[0], 2, 2))

        # Lowpass filter for distant squall thunder (55 Hz)
        self.sos_thunder = signal.butter(2, 55.0, btype='lowpass',
                                         fs=self.sample_rate, output='sos')
        self.zi_thunder = np.zeros((self.sos_thunder.shape[0], 2, 2))
        self.thunder_phase = random.uniform(0, 2 * np.pi)

    def set_intensity(self, intensity):
        self.intensity = max(0.0, min(1.0, float(intensity)))

    def generate(self, n_samples, pink_chunk, white_chunk, brown_chunk):
        # Smoothly slew gain to target intensity
        target = self.intensity
        self.current_gain += (target - self.current_gain) * 0.08
        if self.current_gain < 0.005:
            return np.zeros((n_samples, 2))

        # 1. Surface droplet spray
        spray, self.zi_spray = signal.sosfilt(self.sos_rain_spray, pink_chunk,
                                              axis=0, zi=self.zi_spray)

        # 2. Granular micro-droplet impact modulation (Poisson-like density)
        impact_density = 0.15 + self.current_gain * 0.45
        mask = (np.random.rand(n_samples, 2) < impact_density).astype(np.float32)
        droplets_raw = white_chunk * mask * 2.2
        droplets, self.zi_droplets = signal.sosfilt(self.sos_droplets, droplets_raw,
                                                    axis=0, zi=self.zi_droplets)

        # 3. Distant squall rumble (only at higher rain intensities)
        thunder_audio = np.zeros((n_samples, 2))
        if self.current_gain > 0.4:
            self.thunder_phase += (2 * np.pi * 0.04) * (n_samples / self.sample_rate)
            self.thunder_phase %= (2 * np.pi)
            t_mod = (0.5 + 0.5 * np.sin(self.thunder_phase)) ** 3.0
            thunder_raw = brown_chunk * t_mod * (self.current_gain - 0.4) * 1.5
            thunder_audio, self.zi_thunder = signal.sosfilt(
                self.sos_thunder, thunder_raw, axis=0, zi=self.zi_thunder)

        rain_mix = (spray * 0.45 + droplets * 0.55 + thunder_audio * 0.40) * self.current_gain
        return rain_mix


class NightFaunaGenerator:
    """
    Nocturnal Coastal Soundscape DSP.
    Procedural Hawaiian coastal tree crickets (Laupala) pulsating in
    coastal kiawe groves.
    """
    def __init__(self, sample_rate=SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.phase1 = random.uniform(0, 2 * np.pi)
        self.phase2 = random.uniform(0, 2 * np.pi)
        self.lfo_phase = random.uniform(0, 2 * np.pi)
        self.pulse_phase = random.uniform(0, 2 * np.pi)
        self.gain = 0.0

    def set_night_blend(self, blend):
        """0.0 = daytime (silent), 1.0 = deep night (active nocturnal crickets)."""
        self.gain = max(0.0, min(1.0, float(blend)))

    def generate(self, n_samples):
        if self.gain < 0.005:
            return np.zeros((n_samples, 2))

        dt = 1.0 / self.sample_rate
        t = np.arange(n_samples) * dt

        # High frequency cricket resonance tones (~5.4 kHz and ~6.2 kHz)
        f1 = 5420.0
        f2 = 6180.0

        # Fast cricket pulse rhythm (~14 Hz AM)
        pulse = (0.5 + 0.5 * np.sin(2 * np.pi * 14.5 * t + self.pulse_phase)) ** 4.0
        self.pulse_phase = (self.pulse_phase + 2 * np.pi * 14.5 * n_samples * dt) % (2 * np.pi)

        # Slower breathing cluster modulation (~0.28 Hz)
        cluster = (0.5 + 0.5 * np.sin(2 * np.pi * 0.28 * t + self.lfo_phase)) ** 2.0
        self.lfo_phase = (self.lfo_phase + 2 * np.pi * 0.28 * n_samples * dt) % (2 * np.pi)

        carrier1 = np.sin(2 * np.pi * f1 * t + self.phase1)
        carrier2 = np.sin(2 * np.pi * f2 * t + self.phase2)
        self.phase1 = (self.phase1 + 2 * np.pi * f1 * n_samples * dt) % (2 * np.pi)
        self.phase2 = (self.phase2 + 2 * np.pi * f2 * n_samples * dt) % (2 * np.pi)

        crickets_l = (carrier1 * 0.65 + carrier2 * 0.35) * pulse * cluster * self.gain * 0.045
        crickets_r = (carrier1 * 0.35 + carrier2 * 0.65) * pulse * cluster * self.gain * 0.045

        return np.column_stack((crickets_l, crickets_r))


class WaveEvent:
    """A single procedural ocean wave with swell, crest, dump, foam sizzle,
       backwash drag, and coastal acoustics."""

    def __init__(self, preset, intensity=1.0, period_mult=1.0, pan_dir=None):
        self.preset = preset
        self.intensity = intensity
        p_min = preset.get('wave_period_min', 10.0) * period_mult
        p_max = preset.get('wave_period_max', 15.0) * period_mult
        self.period = random.uniform(p_min, p_max)
        self.duration = self.period * 1.45
        self.break_time = self.period * random.uniform(0.30, 0.38)
        self.age = 0.0
        self.active = True

        # Shoreline peeling progression (stereo drift)
        if pan_dir is None:
            pan_dir = 1.0 if random.random() > 0.5 else -1.0
        self.pan_start = -0.75 * pan_dir * random.uniform(0.7, 1.0)
        self.pan_end = 0.85 * pan_dir * random.uniform(0.7, 1.0)

        # Randomize foam bubble modulation frequency
        self.bubble_freq = random.uniform(11.0, 19.0)
        self.bubble_phase = random.uniform(0, 2 * np.pi)

        # Volcanic blowhole trigger for Waʻānapanapa
        self.has_blowhole = (random.random() < preset.get('blowhole_gain', 0.0))
        self.blowhole_offset = random.uniform(0.1, 0.6)

        # Backwash start scaled to wave duration (was fixed 3.6s)
        self.backwash_start = self.break_time + self.duration * 0.12

    def step(self, n_samples, dt, pink_chunk, white_chunk, brown_chunk):
        t_start = self.age
        t_end = self.age + n_samples * dt
        t_arr = np.linspace(t_start, t_end, n_samples, endpoint=False)
        self.age = t_end

        if t_start >= self.duration:
            self.active = False
            return np.zeros((n_samples, 2))

        # ── 1. Swell Buildup Envelope ──
        swell_attack = np.clip(t_arr / (self.break_time + 1e-5), 0, 1)
        swell_env = (np.sin(swell_attack * (np.pi * 0.5)) ** 2.2)
        swell_decay = np.clip((t_arr - self.break_time) / (self.duration - self.break_time + 1e-5), 0, 1)
        swell_env = swell_env * np.exp(-swell_decay * 2.8) * self.intensity * 1.6

        # ── 2. Breaker Crash Envelope ──
        t_rel_break = t_arr - self.break_time
        breaker_env = np.zeros(n_samples)

        pre_mask = (t_rel_break >= -1.0) & (t_rel_break < 0)
        if np.any(pre_mask):
            tau_pre = (t_rel_break[pre_mask] + 1.0) / 1.0
            breaker_env[pre_mask] = (tau_pre ** 3.0) * 0.4

        post_mask = (t_rel_break >= 0)
        if np.any(post_mask):
            tau = t_rel_break[post_mask]
            peak_t = 0.45
            decay_rate = self.preset.get('breaker_decay', 0.40)
            surge = np.maximum(0, (tau / peak_t) * np.exp(1.0 - (tau / peak_t))) ** 1.3
            breaker_env[post_mask] = surge * np.exp(-tau * decay_rate)

        breaker_env = breaker_env * self.intensity * self.preset.get('breaker_gain', 0.8)

        # ── 3. Hollow Reef Barrel Resonance ──
        hollow_gain = self.preset.get('hollow_barrel_gain', 0.0)
        hollow_env = np.zeros(n_samples)
        if hollow_gain > 0.01:
            hollow_mask = (t_rel_break >= -0.3) & (t_rel_break < 1.8)
            if np.any(hollow_mask):
                tau_h = t_rel_break[hollow_mask] + 0.3
                hollow_env[hollow_mask] = (
                    np.sin(np.pi * np.clip(tau_h / 2.1, 0, 1)) ** 2.0
                ) * hollow_gain * self.intensity

        # ── 4. Shorebreak Thud ──
        thud_env = np.zeros(n_samples)
        thud_mask = (t_rel_break >= 0) & (t_rel_break < 1.2)
        if np.any(thud_mask):
            tau_thud = t_rel_break[thud_mask]
            thud_env[thud_mask] = (
                np.sin(2 * np.pi * 55.0 * tau_thud)
                * np.exp(-tau_thud * 5.0)
                * self.preset.get('shorebreak_thud', 0.3)
                * self.intensity
            )

        # ── 5. Volcanic Blowhole Cavern Surge ──
        blowhole_env = np.zeros(n_samples)
        if self.has_blowhole:
            t_bh = t_rel_break - self.blowhole_offset
            bh_mask = (t_bh >= 0) & (t_bh < 1.8)
            if np.any(bh_mask):
                tau_bh = t_bh[bh_mask]
                blowhole_env[bh_mask] = (
                    np.sin(2 * np.pi * 42.0 * tau_bh)
                    * np.exp(-tau_bh * 3.2)
                    * self.preset.get('blowhole_gain', 0.5)
                    * self.intensity
                )

        # ── 6. Swash Foam Fizz ──
        foam_env = np.zeros(n_samples)
        foam_mask = (t_rel_break >= 0.6)
        if np.any(foam_mask):
            t_foam = t_rel_break[foam_mask] - 0.6
            foam_rise = np.clip(t_foam / 1.8, 0, 1)
            foam_decay = np.exp(-t_foam * self.preset.get('foam_decay', 0.25))
            foam_env[foam_mask] = (foam_rise ** 1.4) * foam_decay
        foam_env = foam_env * self.intensity * self.preset.get('foam_gain', 0.8)

        # ── 7. Backwash Undertow Drag (scaled to wave duration) ──
        bw_env = np.zeros(n_samples)
        bw_mask = (t_arr >= self.backwash_start)
        if np.any(bw_mask):
            t_bw = t_arr[bw_mask] - self.backwash_start
            bw_rise = np.clip(t_bw / 2.2, 0, 1)
            bw_decay = np.exp(-t_bw * 0.32)
            bw_env[bw_mask] = bw_rise * bw_decay
        bw_env = bw_env * self.intensity * self.preset.get('backwash_gain', 0.4)

        # ── 8. Basalt Pebble & Shingle Drag Texture ──
        pebble_gain = self.preset.get('pebble_drag_gain', 0.0)
        pebble_env = np.zeros(n_samples)
        if pebble_gain > 0.01 and np.any(bw_mask):
            pebble_rattle = np.random.uniform(0.7, 1.3, np.sum(bw_mask))
            pebble_env[bw_mask] = bw_env[bw_mask] * pebble_rattle * pebble_gain

        # ── Granular bubble texture modulation ──
        bubble_mod = 1.0 + 0.30 * np.sin(2 * np.pi * self.bubble_freq * t_arr + self.bubble_phase)
        foam_textured = (foam_env * bubble_mod)[:, None]

        # ── Stereo Panning ──
        progress = np.clip(t_arr / self.duration, 0, 1)
        pan = self.pan_start + (self.pan_end - self.pan_start) * progress
        pan_angle = (pan + 1.0) * (np.pi / 4.0)
        pan_l = np.cos(pan_angle)
        pan_r = np.sin(pan_angle)

        # ── Layer summing ──
        layer_swell = pink_chunk * swell_env[:, None] * 1.3
        layer_breaker = (pink_chunk * 0.60 + white_chunk * 0.40) * breaker_env[:, None]
        layer_hollow = pink_chunk * hollow_env[:, None] * 0.80
        layer_foam = (white_chunk * 0.82 + pink_chunk * 0.18) * foam_textured * 0.85
        layer_bw = pink_chunk * bw_env[:, None] * 0.65
        layer_pebble = (white_chunk * 0.65 + pink_chunk * 0.35) * pebble_env[:, None] * 0.70
        layer_thud = np.column_stack((thud_env, thud_env)) * 0.8
        layer_blowhole = (brown_chunk * 0.7 + pink_chunk * 0.3) * blowhole_env[:, None] * 1.1

        wave_l = (layer_swell[:, 0] + layer_breaker[:, 0] + layer_hollow[:, 0]
                  + layer_foam[:, 0] + layer_bw[:, 0] + layer_pebble[:, 0]
                  + layer_thud[:, 0] + layer_blowhole[:, 0]) * pan_l
        wave_r = (layer_swell[:, 1] + layer_breaker[:, 1] + layer_hollow[:, 1]
                  + layer_foam[:, 1] + layer_bw[:, 1] + layer_pebble[:, 1]
                  + layer_thud[:, 1] + layer_blowhole[:, 1]) * pan_r

        return np.column_stack((wave_l, wave_r))


# ═══════════════════════════════════════════════════════════════════════════════
# Hawaiian Ocean Synthesizer
# ═══════════════════════════════════════════════════════════════════════════════

class HawaiianOceanSynthesizer:
    """
    High-fidelity generative acoustic soundscape for Hawaiian coastal environments.
    Uses a background-thread TelemetryManager for non-blocking NOAA buoy/wind/rain
    data, circadian diurnal shifts, tropical rain squalls, and smooth preset
    morphing / shuffle.
    """

    PRESETS = {
        # ── Maui ──
        'napili': {
            'island': 'Maui',
            'name': 'Napili Bay & Kapalua Coves (Gentle, Sheltered & Calming)',
            'wave_period_min': 9.5, 'wave_period_max': 14.5,
            'breaker_gain': 0.65, 'breaker_decay': 0.42,
            'foam_gain': 0.80, 'foam_decay': 0.26,
            'backwash_gain': 0.42, 'swell_bed_gain': 0.35,
            'wind_gain': 0.22, 'wind_lfo_speed': 0.07,
            'wildlife_prob': 0.15, 'wildlife_type': 'kolea',
            'shorebreak_thud': 0.20, 'outer_reef_gain': 0.0,
            'description': 'Calm turquoise cove; gentle rhythmic swash, soft coral sand percolation, and warm light trade breeze.',
        },
        'makena': {
            'island': 'Maui',
            'name': 'Makena / Big Beach (Powerful Shorebreak & Deep Pacific Swell)',
            'wave_period_min': 11.0, 'wave_period_max': 17.0,
            'breaker_gain': 1.15, 'breaker_decay': 0.36,
            'foam_gain': 1.00, 'foam_decay': 0.20,
            'backwash_gain': 0.75, 'swell_bed_gain': 0.65,
            'wind_gain': 0.30, 'wind_lfo_speed': 0.09,
            'wildlife_prob': 0.08, 'wildlife_type': 'kolea',
            'shorebreak_thud': 0.85, 'outer_reef_gain': 0.0,
            'description': 'Golden sand expanse with booming Pacific shorebreak thuds, deep low-end resonance, and textured churning backwash.',
        },
        'northshore': {
            'island': 'Maui',
            'name': 'Paia & Hookipa North Shore (Breezy Trade Winds & Rolling Outer Reef Surf)',
            'wave_period_min': 8.5, 'wave_period_max': 13.5,
            'breaker_gain': 0.92, 'breaker_decay': 0.48,
            'foam_gain': 0.90, 'foam_decay': 0.30,
            'backwash_gain': 0.58, 'swell_bed_gain': 0.52,
            'wind_gain': 0.55, 'wind_lfo_speed': 0.13,
            'wildlife_prob': 0.18, 'wildlife_type': 'seabird',
            'shorebreak_thud': 0.45, 'outer_reef_gain': 0.25,
            'description': 'Rolling Pacific surf lines across outer reefs, steady Hawaiian trade winds whispering through ironwood pines.',
        },
        'keawakapu': {
            'island': 'Maui',
            'name': 'Keawakapu & Wailea (Warm Sunset Serenity)',
            'wave_period_min': 12.0, 'wave_period_max': 18.0,
            'breaker_gain': 0.52, 'breaker_decay': 0.38,
            'foam_gain': 0.70, 'foam_decay': 0.22,
            'backwash_gain': 0.38, 'swell_bed_gain': 0.30,
            'wind_gain': 0.18, 'wind_lfo_speed': 0.05,
            'wildlife_prob': 0.12, 'wildlife_type': 'kolea',
            'shorebreak_thud': 0.15, 'outer_reef_gain': 0.0,
            'description': 'Ultra-peaceful South Maui sunset shoreline; slow rhythmic wave sets, fine sand percolation, and soft evening lull.',
        },
        'honolua': {
            'island': 'Maui',
            'name': 'Honolua Bay & Point Break (Right-Hand Barrels & Canopy Winds)',
            'wave_period_min': 12.0, 'wave_period_max': 17.5,
            'breaker_gain': 1.05, 'breaker_decay': 0.38,
            'foam_gain': 1.05, 'foam_decay': 0.22,
            'backwash_gain': 0.50, 'swell_bed_gain': 0.60,
            'wind_gain': 0.35, 'wind_lfo_speed': 0.08,
            'wildlife_prob': 0.20, 'wildlife_type': 'koae_kea',
            'shorebreak_thud': 0.35, 'outer_reef_gain': 0.45,
            'hollow_barrel_gain': 0.55,
            'description': 'Lush valley amphitheater with long-period northwest swell wrapping into perfect peeling hollow reef barrels and winds rustling through ironwood and mango canopies.',
        },
        'waianapanapa': {
            'island': 'Maui',
            'name': 'Waʻānapanapa Black Sand Beach & Lava Tubes (Volcanic Shingle & Blowholes)',
            'wave_period_min': 10.0, 'wave_period_max': 15.5,
            'breaker_gain': 1.10, 'breaker_decay': 0.42,
            'foam_gain': 0.85, 'foam_decay': 0.25,
            'backwash_gain': 0.85, 'swell_bed_gain': 0.70,
            'wind_gain': 0.40, 'wind_lfo_speed': 0.11,
            'wildlife_prob': 0.15, 'wildlife_type': 'seabird',
            'shorebreak_thud': 0.75, 'outer_reef_gain': 0.20,
            'pebble_drag_gain': 0.75, 'blowhole_gain': 0.65,
            'description': 'Dramatic East Maui black basalt pebble beach with deep cavernous blowhole surges, sea-cave echoes, and coarse volcanic shingle undertow friction.',
        },
        'la-perouse': {
            'island': 'Maui',
            'name': 'Keoneʻōʻio / La Perouse Bay (South Maui Aʻā Lava Ledges & Channel Swell)',
            'wave_period_min': 11.5, 'wave_period_max': 17.0,
            'breaker_gain': 1.18, 'breaker_decay': 0.35,
            'foam_gain': 0.95, 'foam_decay': 0.20,
            'backwash_gain': 0.60, 'swell_bed_gain': 0.72,
            'wind_gain': 0.50, 'wind_lfo_speed': 0.14,
            'wildlife_prob': 0.08, 'wildlife_type': 'seabird',
            'shorebreak_thud': 0.95, 'outer_reef_gain': 0.15,
            'description': 'Jagged black aʻā lava coast facing the Alenuihāhā channel; raw ocean swells slamming directly into volcanic rock ledges with fierce spray and isolated winds.',
        },
        'molokini': {
            'island': 'Maui',
            'name': 'Molokini Crater & Caldera Reef (Pelagic 360° Swell Wrap & Seabird Haven)',
            'wave_period_min': 12.5, 'wave_period_max': 19.0,
            'breaker_gain': 0.70, 'breaker_decay': 0.45,
            'foam_gain': 0.80, 'foam_decay': 0.30,
            'backwash_gain': 0.10, 'swell_bed_gain': 0.80,
            'wind_gain': 0.42, 'wind_lfo_speed': 0.10,
            'wildlife_prob': 0.28, 'wildlife_type': 'seabird',
            'shorebreak_thud': 0.15, 'outer_reef_gain': 0.60,
            'description': 'Offshore crescent caldera with 360-degree open-ocean swell wrap, pure deep blue pelagic acoustic mass, crisp barrier reef wash, and wheeling seabirds.',
        },

        # ── Kauaʻi ──
        'hanalei': {
            'island': 'Kauaʻi',
            'name': 'Hanalei Bay (Grand North Shore Crescent & Mountain Amphitheater)',
            'wave_period_min': 13.0, 'wave_period_max': 19.0,
            'breaker_gain': 0.85, 'breaker_decay': 0.40,
            'foam_gain': 0.95, 'foam_decay': 0.24,
            'backwash_gain': 0.55, 'swell_bed_gain': 0.58,
            'wind_gain': 0.28, 'wind_lfo_speed': 0.06,
            'wildlife_prob': 0.20, 'wildlife_type': 'koae_kea',
            'shorebreak_thud': 0.40, 'outer_reef_gain': 0.35,
            'description': 'Grand emerald crescent bay framed by waterfalls; long-period North Pacific swells peeling majestically across the rivermouth with lush mountain amphitheater mist.',
        },
        'polihale': {
            'island': 'Kauaʻi',
            'name': 'Polihale & Barking Sands (Booming Dune Surf & Open Channel Winds)',
            'wave_period_min': 10.5, 'wave_period_max': 16.5,
            'breaker_gain': 1.25, 'breaker_decay': 0.34,
            'foam_gain': 1.10, 'foam_decay': 0.18,
            'backwash_gain': 0.90, 'swell_bed_gain': 0.75,
            'wind_gain': 0.65, 'wind_lfo_speed': 0.15,
            'wildlife_prob': 0.05, 'wildlife_type': 'kolea',
            'shorebreak_thud': 0.95, 'outer_reef_gain': 0.15,
            'description': 'Massive 17-mile desert dune coast facing the Niʻihau channel; thunderous shorebreak pounding steep white dunes with dry roaring winds.',
        },
        'kee': {
            'island': 'Kauaʻi',
            'name': 'Keʻe Beach & Na Pali Gateway (Outer Barrier Reef & Crystal Lagoon)',
            'wave_period_min': 11.0, 'wave_period_max': 17.0,
            'breaker_gain': 0.45, 'breaker_decay': 0.50,
            'foam_gain': 0.75, 'foam_decay': 0.28,
            'backwash_gain': 0.35, 'swell_bed_gain': 0.50,
            'wind_gain': 0.32, 'wind_lfo_speed': 0.08,
            'wildlife_prob': 0.25, 'wildlife_type': 'koae_kea',
            'shorebreak_thud': 0.18, 'outer_reef_gain': 0.70,
            'description': 'Dramatic Na Pali sea cliff backdrop; deep rolling outer reef breaks 200m offshore with a tranquil, crystal lagoon lapping gently against coral sands and ironwoods.',
        },
        'poipu': {
            'island': 'Kauaʻi',
            'name': 'Poipu Beach (Sunny South Shore Tombolo & Coral Coves)',
            'wave_period_min': 9.0, 'wave_period_max': 14.0,
            'breaker_gain': 0.58, 'breaker_decay': 0.44,
            'foam_gain': 0.82, 'foam_decay': 0.25,
            'backwash_gain': 0.40, 'swell_bed_gain': 0.32,
            'wind_gain': 0.20, 'wind_lfo_speed': 0.07,
            'wildlife_prob': 0.14, 'wildlife_type': 'kolea',
            'shorebreak_thud': 0.22, 'outer_reef_gain': 0.18,
            'description': 'Sunny golden tombolo split by coral reefs; rhythmic gentle surf lapping sheltered sandy lagoons with warm afternoon trade breezes.',
        },
        'anini': {
            'island': 'Kauaʻi',
            'name': 'Anini Beach (Widest Fringing Barrier Reef & Glassy Lagoon)',
            'wave_period_min': 12.0, 'wave_period_max': 18.0,
            'breaker_gain': 0.30, 'breaker_decay': 0.55,
            'foam_gain': 0.65, 'foam_decay': 0.32,
            'backwash_gain': 0.25, 'swell_bed_gain': 0.45,
            'wind_gain': 0.24, 'wind_lfo_speed': 0.06,
            'wildlife_prob': 0.16, 'wildlife_type': 'seabird',
            'shorebreak_thud': 0.10, 'outer_reef_gain': 0.85,
            'description': "Hawaii's widest protective fringing reef; constant distant white-water roar 400m offshore paired with ultra-tranquil glassy ripples along shallow sandy channels.",
        },
    }

    def __init__(self, preset_name='napili', sample_rate=48000,
                 enable_live=True, circadian_mode='auto', rain_intensity=None):
        if preset_name not in self.PRESETS:
            preset_name = 'napili'
        self.preset_name = preset_name
        self.preset = dict(self.PRESETS[preset_name])
        self.sample_rate = sample_rate
        self.dt = 1.0 / sample_rate

        self.pink_gen = FastPinkNoise(channels=2)
        self.brown_gen = FastBrownNoise(channels=2, leak=0.996)

        # Environmental DSP engines
        self.rain_gen = RainGenerator(sample_rate=sample_rate)
        self.night_fauna = NightFaunaGenerator(sample_rate=sample_rate)

        # Diurnal and Telemetry parameters
        self.enable_live = enable_live
        self.circadian_mode = circadian_mode  # 'auto', 'dawn', 'day', 'sunset', 'night', 'off'
        self.forced_rain_intensity = rain_intensity

        # ── Background telemetry manager (non-blocking) ──
        self._telem_mgr = get_telemetry_manager()
        if enable_live:
            island = self.preset.get('island', 'Maui')
            self._telem_mgr.configure(island=island)
            self._telem_mgr.start()

        # Live multipliers (default neutral)
        self.live_multipliers = {
            'swell_gain_mult': 1.0,
            'wave_period_mult': 1.0,
            'wind_gain_mult': 1.0,
            'rain_intensity': 0.0,
        }
        self.last_telemetry = None

        # Circadian DSP overrides
        self.diurnal_wind_mult = 1.0
        self.diurnal_swell_mult = 1.0
        self.diurnal_bird_mult = 1.0

        self.active_waves = []
        self.time_to_next_wave = 0.5
        self.current_time = 0.0

        # Swell sets (3-5 waves followed by a quieter lull)
        self.in_set = True
        self.waves_in_current_set = random.randint(3, 5)
        self.waves_spawned_in_set = 0

        # Wind LFO phases
        self.wind_phase1 = random.uniform(0, 2 * np.pi)
        self.wind_phase2 = random.uniform(0, 2 * np.pi)

        # Outer Barrier Reef Swell LFO
        self.outer_reef_phase = random.uniform(0, 2 * np.pi)

        # Wildlife
        self.active_bird_calls = []

        # ── Master DSP filters ──
        # Lowpass filter for ocean floor swell bed (110 Hz)
        self.sos_ocean_bed = signal.butter(2, 110.0, btype='lowpass',
                                           fs=self.sample_rate, output='sos')
        self.zi_ocean_bed = np.zeros((self.sos_ocean_bed.shape[0], 2, 2))

        # Bandpass filter for wind (85–750 Hz)
        self.sos_wind = signal.butter(2, [85.0, 750.0], btype='bandpass',
                                      fs=self.sample_rate, output='sos')
        self.zi_wind = np.zeros((self.sos_wind.shape[0], 2, 2))

        # Lowpass filter for distant outer barrier reef break (420 Hz)
        self.sos_outer_reef = signal.butter(2, 420.0, btype='lowpass',
                                            fs=self.sample_rate, output='sos')
        self.zi_outer_reef = np.zeros((self.sos_outer_reef.shape[0], 2, 2))

        # Initial circadian phase update (no network needed)
        self._update_circadian_dsp()

    # ── preset management ──

    def set_preset(self, preset_name):
        """Morph active acoustic characteristics to a new beach preset."""
        if preset_name in self.PRESETS:
            self.preset_name = preset_name
            self.preset = dict(self.PRESETS[preset_name])
            if self.enable_live:
                island = self.preset.get('island', 'Maui')
                self._telem_mgr.configure(island=island)
                logger.info("Switched to preset '%s' (island=%s)", preset_name, island)

    # ── telemetry & circadian (non-blocking) ──

    def refresh_telemetry(self):
        """
        Read latest multipliers from the background TelemetryManager.
        This call NEVER blocks — it just copies the latest pre-fetched values.
        Also updates circadian phase and rain intensity.
        """
        try:
            # Non-blocking: just read what the background thread has cached
            if self.enable_live:
                self.live_multipliers = self._telem_mgr.get_multipliers()
            self.last_telemetry = self._telem_mgr.get_telemetry()

            # Update rain generator
            if self.forced_rain_intensity is not None:
                self.rain_gen.set_intensity(self.forced_rain_intensity)
            elif self.enable_live:
                self.rain_gen.set_intensity(
                    self.live_multipliers.get('rain_intensity', 0.0))

            # Update circadian phase
            self._update_circadian_dsp()
        except Exception:
            logger.warning("refresh_telemetry failed", exc_info=True)

    def _update_circadian_dsp(self):
        """Calculates circadian lighting/atmosphere multipliers."""
        phase = self.circadian_mode
        if phase == 'auto':
            phase, _ = determine_circadian_phase()

        if phase == 'night':
            self.night_fauna.set_night_blend(1.0)
            self.diurnal_wind_mult = 0.75
            self.diurnal_swell_mult = 1.15
            self.diurnal_bird_mult = 0.0
        elif phase == 'dawn':
            self.night_fauna.set_night_blend(0.2)
            self.diurnal_wind_mult = 0.65
            self.diurnal_swell_mult = 0.95
            self.diurnal_bird_mult = 1.4
        elif phase == 'sunset':
            self.night_fauna.set_night_blend(0.4)
            self.diurnal_wind_mult = 0.85
            self.diurnal_swell_mult = 1.05
            self.diurnal_bird_mult = 0.8
        elif phase == 'day':
            self.night_fauna.set_night_blend(0.0)
            self.diurnal_wind_mult = 1.15
            self.diurnal_swell_mult = 1.0
            self.diurnal_bird_mult = 1.0
        else:  # 'off'
            self.night_fauna.set_night_blend(0.0)
            self.diurnal_wind_mult = 1.0
            self.diurnal_swell_mult = 1.0
            self.diurnal_bird_mult = 1.0

    # ── wildlife ──

    def _spawn_bird_call(self):
        """Generates species-accurate procedural calls (Kōlea, Koaʻe kea, Noio)."""
        bird_type = self.preset.get('wildlife_type', 'kolea')

        if bird_type == 'koae_kea':
            # Koaʻe kea (White-tailed Tropicbird) — high undulating aerial trill
            duration = random.uniform(0.8, 1.4)
            n_samples = int(duration * self.sample_rate)
            t = np.linspace(0, duration, n_samples)
            f_center = random.uniform(3200, 3600)
            f_mod = 550 * np.sin(np.pi * np.clip(t / duration, 0, 1))
            vibrato = 60 * np.sin(2 * np.pi * 18.0 * t)
            freq = f_center + f_mod + vibrato
            env = (np.sin(np.pi * np.clip(t / duration, 0, 1)) ** 2.0)
            phase = 2 * np.pi * np.cumsum(freq) / self.sample_rate
            mono_call = np.sin(phase) * env * 0.045
        elif bird_type == 'seabird':
            # Noio (Brown Noddy) / Shearwater — soft churring oceanic trill
            duration = random.uniform(0.5, 0.9)
            n_samples = int(duration * self.sample_rate)
            t = np.linspace(0, duration, n_samples)
            f_center = random.uniform(1900, 2400)
            trill = 120 * np.sin(2 * np.pi * 32.0 * t)
            freq = f_center + trill
            env = (np.sin(np.pi * np.clip(t / duration, 0, 1)) ** 1.8)
            phase = 2 * np.pi * np.cumsum(freq) / self.sample_rate
            mono_call = np.sin(phase) * env * 0.040
        else:
            # Kōlea (Pacific Golden-Plover) — pure descending soft slur
            duration = random.uniform(0.65, 1.1)
            n_samples = int(duration * self.sample_rate)
            t = np.linspace(0, duration, n_samples)
            f_start = random.uniform(2200, 2600)
            f_end = f_start - random.uniform(350, 600)
            freq = np.linspace(f_start, f_end, n_samples)
            env = (np.sin(np.pi * np.clip(t / duration, 0, 1)) ** 2.0)
            phase = 2 * np.pi * np.cumsum(freq) / self.sample_rate
            mono_call = np.sin(phase) * env * 0.05

        pan = random.uniform(-0.8, 0.8)
        pan_angle = (pan + 1.0) * (np.pi / 4.0)
        stereo_call = np.column_stack((mono_call * np.cos(pan_angle),
                                       mono_call * np.sin(pan_angle)))
        self.active_bird_calls.append({'audio': stereo_call, 'pos': 0})

    # ── main generation ──

    def generate_chunk(self, n_samples=4096, volume=1.0):
        """
        Generate the next audio buffer chunk in real-time.

        Parameters
        ----------
        n_samples : int
            Number of samples per channel.
        volume : float
            Master volume (0.0–2.0).  Applied *before* soft saturation
            so that values >1.0 are compressed, not hard-clipped.
        """
        volume = max(0.0, min(2.0, float(volume)))
        dt_chunk = n_samples * self.dt
        self.current_time += dt_chunk

        pink_chunk = self.pink_gen.generate(n_samples)
        brown_chunk = self.brown_gen.generate(n_samples)
        white_chunk = np.random.normal(0, 0.75, (n_samples, 2))

        # ── Telemetry & Diurnal scalers ──
        period_mult = self.live_multipliers.get('wave_period_mult', 1.0)
        swell_mult = (self.live_multipliers.get('swell_gain_mult', 1.0)
                      * self.diurnal_swell_mult)
        wind_mult = (self.live_multipliers.get('wind_gain_mult', 1.0)
                     * self.diurnal_wind_mult)
        bird_prob_mult = self.diurnal_bird_mult

        # ── 1. Nearshore Wave Scheduling & Swell Sets ──
        self.time_to_next_wave -= dt_chunk
        if self.time_to_next_wave <= 0:
            if self.in_set:
                intensity = random.uniform(0.9, 1.35) * swell_mult
                self.active_waves.append(WaveEvent(self.preset, intensity=intensity,
                                                   period_mult=period_mult))
                self.waves_spawned_in_set += 1
                if self.waves_spawned_in_set >= self.waves_in_current_set:
                    self.in_set = False
                    self.time_to_next_wave = random.uniform(14.0, 24.0) * period_mult
                else:
                    self.time_to_next_wave = random.uniform(
                        self.preset['wave_period_min'],
                        self.preset['wave_period_max']) * period_mult
            else:
                intensity = random.uniform(0.45, 0.75) * swell_mult
                self.active_waves.append(WaveEvent(self.preset, intensity=intensity,
                                                   period_mult=period_mult))
                self.in_set = True
                self.waves_spawned_in_set = 0
                self.waves_in_current_set = random.randint(3, 5)
                self.time_to_next_wave = random.uniform(
                    self.preset['wave_period_min'],
                    self.preset['wave_period_max']) * period_mult

            # Daytime bird spawn
            if (random.random() < self.preset.get('wildlife_prob', 0.15) * bird_prob_mult
                    and bird_prob_mult > 0.05):
                self._spawn_bird_call()

        # ── Sum nearshore active waves ──
        waves_mix = np.zeros((n_samples, 2))
        for w in self.active_waves:
            if w.active:
                waves_mix += w.step(n_samples, self.dt, pink_chunk, white_chunk, brown_chunk)
        self.active_waves = [w for w in self.active_waves if w.active]

        # ── 2. Continuous Ocean Floor Swell Bed ──
        ocean_bed, self.zi_ocean_bed = signal.sosfilt(
            self.sos_ocean_bed, brown_chunk, axis=0, zi=self.zi_ocean_bed)
        ocean_bed = ocean_bed * (self.preset.get('swell_bed_gain', 0.5) * swell_mult)

        # ── 3. Hawaiian Trade Winds ──
        lfo_spd = self.preset.get('wind_lfo_speed', 0.08)
        self.wind_phase1 = (self.wind_phase1 + 2 * np.pi * lfo_spd * dt_chunk) % (2 * np.pi)
        self.wind_phase2 = (self.wind_phase2 + 2 * np.pi * (lfo_spd * 1.618) * dt_chunk) % (2 * np.pi)
        wind_mod = 0.70 + 0.30 * np.sin(self.wind_phase1) + 0.15 * np.cos(self.wind_phase2)
        wind_audio, self.zi_wind = signal.sosfilt(self.sos_wind, pink_chunk, axis=0, zi=self.zi_wind)
        wind_audio = wind_audio * (wind_mod * self.preset.get('wind_gain', 0.3) * wind_mult)

        # ── 4. Distant Outer Barrier Reef Breakers ──
        outer_reef_gain = self.preset.get('outer_reef_gain', 0.0)
        outer_reef_audio = np.zeros((n_samples, 2))
        if outer_reef_gain > 0.01:
            self.outer_reef_phase = (self.outer_reef_phase
                                     + 2 * np.pi * 0.075 * dt_chunk) % (2 * np.pi)
            reef_swell = (0.65 + 0.35 * np.sin(self.outer_reef_phase)) ** 2.0
            raw_reef = (pink_chunk * 0.7 + brown_chunk * 0.3) * reef_swell
            outer_reef_filtered, self.zi_outer_reef = signal.sosfilt(
                self.sos_outer_reef, raw_reef, axis=0, zi=self.zi_outer_reef)
            outer_reef_audio = outer_reef_filtered * (outer_reef_gain * swell_mult * 0.75)

        # ── 5. Wildlife / Seabirds ──
        birds_mix = np.zeros((n_samples, 2))
        remaining_birds = []
        for bird in self.active_bird_calls:
            b_audio = bird['audio']
            b_pos = bird['pos']
            rem = len(b_audio) - b_pos
            if rem > 0:
                take = min(n_samples, rem)
                birds_mix[:take] += b_audio[b_pos:b_pos + take]
                bird['pos'] += take
                if bird['pos'] < len(b_audio):
                    remaining_birds.append(bird)
        self.active_bird_calls = remaining_birds

        # ── 6. Environmental Layers ──
        rain_audio = self.rain_gen.generate(n_samples, pink_chunk, white_chunk, brown_chunk)
        night_audio = self.night_fauna.generate(n_samples)

        # ── 7. Master Sum & Soft Saturation (volume applied before tanh) ──
        master = (waves_mix * 0.72
                  + ocean_bed * 0.45
                  + wind_audio * 0.35
                  + outer_reef_audio * 0.50
                  + birds_mix
                  + rain_audio * 0.60
                  + night_audio * 0.85)

        # Volume is applied *before* the soft clipper so high volumes are
        # compressed rather than hard-clipped.
        master = np.tanh(master * 0.85 * volume)

        return master


# Backward compatibility alias
MauiOceanSynthesizer = HawaiianOceanSynthesizer
