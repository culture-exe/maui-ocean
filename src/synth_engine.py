#!/usr/bin/env python3
"""
Hawaiian Ocean Beach Generative Acoustic Synthesizer
Fully procedural, real-time DSP physical-acoustic model of Maui and Kauaʻi coastlines.
"""

import sys
import os
import time
import math
import random
import numpy as np
from scipy import signal

SAMPLE_RATE = 48000

class FastPinkNoise:
    """Vectorized 3-pole IIR filter for pristine O(1) pink noise generation."""
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

class WaveEvent:
    """A single procedural ocean wave with swell, crest, dump, foam sizzle, and backwash drag."""
    def __init__(self, preset, intensity=1.0, pan_dir=None):
        self.preset = preset
        self.intensity = intensity
        self.period = random.uniform(preset['wave_period_min'], preset['wave_period_max'])
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

    def step(self, n_samples, dt, pink_chunk, white_chunk):
        t_start = self.age
        t_end = self.age + n_samples * dt
        t_arr = np.linspace(t_start, t_end, n_samples, endpoint=False)
        self.age = t_end
        
        if t_start >= self.duration:
            self.active = False
            return np.zeros((n_samples, 2))

        # 1. Swell Buildup Envelope (Deep pelagic surge rising before break)
        swell_attack = np.clip(t_arr / (self.break_time + 1e-5), 0, 1)
        swell_env = (np.sin(swell_attack * (np.pi * 0.5)) ** 2.2)
        # Decay after break
        swell_decay = np.clip((t_arr - self.break_time) / (self.duration - self.break_time + 1e-5), 0, 1)
        swell_env = swell_env * np.exp(-swell_decay * 2.8) * self.intensity * 1.6

        # 2. Breaker Crash Envelope (The curling lip, impact, rolling turbulence)
        t_rel_break = t_arr - self.break_time
        breaker_env = np.zeros(n_samples)
        
        # Cresting hiss before impact
        pre_mask = (t_rel_break >= -1.0) & (t_rel_break < 0)
        if np.any(pre_mask):
            tau_pre = (t_rel_break[pre_mask] + 1.0) / 1.0
            breaker_env[pre_mask] = (tau_pre ** 3.0) * 0.4
            
        # Post-break turbulent collapse
        post_mask = (t_rel_break >= 0)
        if np.any(post_mask):
            tau = t_rel_break[post_mask]
            peak_t = 0.45
            decay_rate = self.preset['breaker_decay']
            surge = np.maximum(0, (tau / peak_t) * np.exp(1.0 - (tau / peak_t))) ** 1.3
            breaker_env[post_mask] = surge * np.exp(-tau * decay_rate)
            
        breaker_env = breaker_env * self.intensity * self.preset['breaker_gain']

        # 3. Shorebreak Thud (Low-end impact impulse when wave crashes into sand ledge)
        thud_env = np.zeros(n_samples)
        thud_mask = (t_rel_break >= 0) & (t_rel_break < 1.2)
        if np.any(thud_mask):
            tau_thud = t_rel_break[thud_mask]
            thud_env[thud_mask] = np.sin(2 * np.pi * 55.0 * tau_thud) * np.exp(-tau_thud * 5.0) * self.preset['shorebreak_thud'] * self.intensity

        # 4. Swash Foam Fizz (Billions of bursting microbubbles spreading up beach)
        foam_env = np.zeros(n_samples)
        foam_mask = (t_rel_break >= 0.6)
        if np.any(foam_mask):
            t_foam = t_rel_break[foam_mask] - 0.6
            foam_rise = np.clip(t_foam / 1.8, 0, 1)
            foam_decay = np.exp(-t_foam * self.preset['foam_decay'])
            foam_env[foam_mask] = (foam_rise ** 1.4) * foam_decay
        foam_env = foam_env * self.intensity * self.preset['foam_gain']

        # 5. Backwash Undertow Drag (Water percolating through coral & sand grains back to sea)
        bw_env = np.zeros(n_samples)
        bw_start = self.break_time + 3.6
        bw_mask = (t_arr >= bw_start)
        if np.any(bw_mask):
            t_bw = t_arr[bw_mask] - bw_start
            bw_rise = np.clip(t_bw / 2.2, 0, 1)
            bw_decay = np.exp(-t_bw * 0.32)
            bw_env[bw_mask] = bw_rise * bw_decay
        bw_env = bw_env * self.intensity * self.preset['backwash_gain']

        # Granular bubble texture modulation
        bubble_mod = 1.0 + 0.30 * np.sin(2 * np.pi * self.bubble_freq * t_arr + self.bubble_phase)
        foam_textured = (foam_env * bubble_mod)[:, None]

        # Stereo Panning progression across shore
        progress = np.clip(t_arr / self.duration, 0, 1)
        pan = self.pan_start + (self.pan_end - self.pan_start) * progress
        pan_angle = (pan + 1.0) * (np.pi / 4.0)
        pan_l = np.cos(pan_angle)
        pan_r = np.sin(pan_angle)

        # Layer summing
        layer_swell = pink_chunk * swell_env[:, None] * 1.3
        layer_breaker = (pink_chunk * 0.60 + white_chunk * 0.40) * breaker_env[:, None]
        layer_foam = (white_chunk * 0.82 + pink_chunk * 0.18) * foam_textured * 0.85
        layer_bw = pink_chunk * bw_env[:, None] * 0.65
        layer_thud = np.column_stack((thud_env, thud_env)) * 0.8

        wave_l = (layer_swell[:, 0] + layer_breaker[:, 0] + layer_foam[:, 0] + layer_bw[:, 0] + layer_thud[:, 0]) * pan_l
        wave_r = (layer_swell[:, 1] + layer_breaker[:, 1] + layer_foam[:, 1] + layer_bw[:, 1] + layer_thud[:, 1]) * pan_r

        return np.column_stack((wave_l, wave_r))


class HawaiianOceanSynthesizer:
    """High-fidelity procedural acoustic landscape for Maui and Kauaʻi beaches."""
    
    PRESETS = {
        # --- MAUI PRESETS ---
        'napili': {
            'island': 'Maui',
            'name': 'Napili Bay & Kapalua Coves (Gentle, Sheltered & Calming)',
            'wave_period_min': 9.5,
            'wave_period_max': 14.5,
            'breaker_gain': 0.65,
            'breaker_decay': 0.42,
            'foam_gain': 0.80,
            'foam_decay': 0.26,
            'backwash_gain': 0.42,
            'swell_bed_gain': 0.35,
            'wind_gain': 0.22,
            'wind_lfo_speed': 0.07,
            'wildlife_prob': 0.15,
            'wildlife_type': 'kolea',
            'shorebreak_thud': 0.20,
            'outer_reef_gain': 0.0,
            'description': 'Calm turquoise cove; gentle rhythmic swash, soft coral sand percolation, and warm light trade breeze.'
        },
        'makena': {
            'island': 'Maui',
            'name': 'Makena / Big Beach (Powerful Shorebreak & Deep Pacific Swell)',
            'wave_period_min': 11.0,
            'wave_period_max': 17.0,
            'breaker_gain': 1.15,
            'breaker_decay': 0.36,
            'foam_gain': 1.00,
            'foam_decay': 0.20,
            'backwash_gain': 0.75,
            'swell_bed_gain': 0.65,
            'wind_gain': 0.30,
            'wind_lfo_speed': 0.09,
            'wildlife_prob': 0.08,
            'wildlife_type': 'kolea',
            'shorebreak_thud': 0.85,
            'outer_reef_gain': 0.0,
            'description': 'Golden sand expanse with booming Pacific shorebreak thuds, deep low-end resonance, and textured churning backwash.'
        },
        'northshore': {
            'island': 'Maui',
            'name': 'Paia & Hookipa North Shore (Breezy Trade Winds & Rolling Outer Reef Surf)',
            'wave_period_min': 8.5,
            'wave_period_max': 13.5,
            'breaker_gain': 0.92,
            'breaker_decay': 0.48,
            'foam_gain': 0.90,
            'foam_decay': 0.30,
            'backwash_gain': 0.58,
            'swell_bed_gain': 0.52,
            'wind_gain': 0.55,
            'wind_lfo_speed': 0.13,
            'wildlife_prob': 0.18,
            'wildlife_type': 'seabird',
            'shorebreak_thud': 0.45,
            'outer_reef_gain': 0.25,
            'description': 'Rolling Pacific surf lines across outer reefs, steady Hawaiian trade winds whispering through ironwood pines.'
        },
        'keawakapu': {
            'island': 'Maui',
            'name': 'Keawakapu & Wailea (Warm Sunset Serenity)',
            'wave_period_min': 12.0,
            'wave_period_max': 18.0,
            'breaker_gain': 0.52,
            'breaker_decay': 0.38,
            'foam_gain': 0.70,
            'foam_decay': 0.22,
            'backwash_gain': 0.38,
            'swell_bed_gain': 0.30,
            'wind_gain': 0.18,
            'wind_lfo_speed': 0.05,
            'wildlife_prob': 0.12,
            'wildlife_type': 'kolea',
            'shorebreak_thud': 0.15,
            'outer_reef_gain': 0.0,
            'description': 'Ultra-peaceful South Maui sunset shoreline; slow rhythmic wave sets, fine sand percolation, and soft evening lull.'
        },

        # --- KAUAʻI PRESETS ---
        'hanalei': {
            'island': 'Kauaʻi',
            'name': 'Hanalei Bay (Grand North Shore Crescent & Mountain Amphitheater)',
            'wave_period_min': 13.0,
            'wave_period_max': 19.0,
            'breaker_gain': 0.85,
            'breaker_decay': 0.40,
            'foam_gain': 0.95,
            'foam_decay': 0.24,
            'backwash_gain': 0.55,
            'swell_bed_gain': 0.58,
            'wind_gain': 0.28,
            'wind_lfo_speed': 0.06,
            'wildlife_prob': 0.20,
            'wildlife_type': 'koae_kea',
            'shorebreak_thud': 0.40,
            'outer_reef_gain': 0.35,
            'description': 'Grand emerald crescent bay framed by waterfalls; long-period North Pacific swells peeling majestically across the rivermouth with lush mountain amphitheater mist.'
        },
        'polihale': {
            'island': 'Kauaʻi',
            'name': 'Polihale & Barking Sands (Booming Dune Surf & Open Channel Winds)',
            'wave_period_min': 10.5,
            'wave_period_max': 16.5,
            'breaker_gain': 1.25,
            'breaker_decay': 0.34,
            'foam_gain': 1.10,
            'foam_decay': 0.18,
            'backwash_gain': 0.90,
            'swell_bed_gain': 0.75,
            'wind_gain': 0.65,
            'wind_lfo_speed': 0.15,
            'wildlife_prob': 0.05,
            'wildlife_type': 'kolea',
            'shorebreak_thud': 0.95,
            'outer_reef_gain': 0.15,
            'description': 'Massive 17-mile desert dune coast facing the Niʻihau channel; thunderous shorebreak pounding steep white dunes with dry roaring winds.'
        },
        'kee': {
            'island': 'Kauaʻi',
            'name': 'Keʻe Beach & Na Pali Gateway (Outer Barrier Reef & Crystal Lagoon)',
            'wave_period_min': 11.0,
            'wave_period_max': 17.0,
            'breaker_gain': 0.45,
            'breaker_decay': 0.50,
            'foam_gain': 0.75,
            'foam_decay': 0.28,
            'backwash_gain': 0.35,
            'swell_bed_gain': 0.50,
            'wind_gain': 0.32,
            'wind_lfo_speed': 0.08,
            'wildlife_prob': 0.25,
            'wildlife_type': 'koae_kea',
            'shorebreak_thud': 0.18,
            'outer_reef_gain': 0.70,
            'description': 'Dramatic Na Pali sea cliff backdrop; deep rolling outer reef breaks 200m offshore with a tranquil, crystal lagoon lapping gently against coral sands and ironwoods.'
        },
        'poipu': {
            'island': 'Kauaʻi',
            'name': 'Poipu Beach (Sunny South Shore Tombolo & Coral Coves)',
            'wave_period_min': 9.0,
            'wave_period_max': 14.0,
            'breaker_gain': 0.58,
            'breaker_decay': 0.44,
            'foam_gain': 0.82,
            'foam_decay': 0.25,
            'backwash_gain': 0.40,
            'swell_bed_gain': 0.32,
            'wind_gain': 0.20,
            'wind_lfo_speed': 0.07,
            'wildlife_prob': 0.14,
            'wildlife_type': 'kolea',
            'shorebreak_thud': 0.22,
            'outer_reef_gain': 0.18,
            'description': 'Sunny golden tombolo split by coral reefs; rhythmic gentle surf lapping sheltered sandy lagoons with warm afternoon trade breezes.'
        },
        'anini': {
            'island': 'Kauaʻi',
            'name': 'Anini Beach (Widest Fringing Barrier Reef & Glassy Lagoon)',
            'wave_period_min': 12.0,
            'wave_period_max': 18.0,
            'breaker_gain': 0.30,
            'breaker_decay': 0.55,
            'foam_gain': 0.65,
            'foam_decay': 0.32,
            'backwash_gain': 0.25,
            'swell_bed_gain': 0.45,
            'wind_gain': 0.24,
            'wind_lfo_speed': 0.06,
            'wildlife_prob': 0.16,
            'wildlife_type': 'seabird',
            'shorebreak_thud': 0.10,
            'outer_reef_gain': 0.85,
            'description': 'Hawaii\'s widest protective fringing reef; constant distant white-water roar 400m offshore paired with ultra-tranquil glassy ripples along shallow sandy channels.'
        }
    }

    def __init__(self, preset_name='napili', sample_rate=48000):
        if preset_name not in self.PRESETS:
            preset_name = 'napili'
        self.preset_name = preset_name
        self.preset = self.PRESETS[preset_name]
        self.sample_rate = sample_rate
        self.dt = 1.0 / sample_rate
        
        self.pink_gen = FastPinkNoise(channels=2)
        self.brown_gen = FastBrownNoise(channels=2, leak=0.996)
        
        self.active_waves = []
        self.time_to_next_wave = 0.5
        self.current_time = 0.0
        
        # Swell sets (3-5 waves followed by a quieter lull)
        self.in_set = True
        self.waves_in_current_set = random.randint(3, 5)
        self.waves_spawned_in_set = 0
        
        # Wind LFO phases
        self.wind_phase1 = random.uniform(0, 2*np.pi)
        self.wind_phase2 = random.uniform(0, 2*np.pi)
        
        # Outer Barrier Reef Swell LFO
        self.outer_reef_phase = random.uniform(0, 2*np.pi)

        # Wildlife
        self.active_bird_calls = []

        # Master DSP filters
        # Lowpass filter for ocean floor swell bed (110 Hz)
        self.sos_ocean_bed = signal.butter(2, 110.0, btype='lowpass', fs=self.sample_rate, output='sos')
        self.zi_ocean_bed = np.zeros((self.sos_ocean_bed.shape[0], 2, 2))
        
        # Bandpass filter for wind (85 Hz - 750 Hz)
        self.sos_wind = signal.butter(2, [85.0, 750.0], btype='bandpass', fs=self.sample_rate, output='sos')
        self.zi_wind = np.zeros((self.sos_wind.shape[0], 2, 2))

        # Lowpass filter for distant outer barrier reef break (420 Hz, atmospheric HF absorption)
        self.sos_outer_reef = signal.butter(2, 420.0, btype='lowpass', fs=self.sample_rate, output='sos')
        self.zi_outer_reef = np.zeros((self.sos_outer_reef.shape[0], 2, 2))

    def set_preset(self, preset_name):
        if preset_name in self.PRESETS:
            self.preset_name = preset_name
            self.preset = self.PRESETS[preset_name]

    def _spawn_bird_call(self):
        """Generates species-accurate procedural calls (Kōlea or Koaʻe kea / White-tailed Tropicbird)."""
        bird_type = self.preset.get('wildlife_type', 'kolea')
        
        if bird_type == 'koae_kea':
            # Koaʻe kea (White-tailed Tropicbird) of Kauaʻi sea cliffs:
            # High-pitched, pure undulating aerial trill/whistle (3.2 kHz -> 4.1 kHz -> 2.8 kHz)
            duration = random.uniform(0.8, 1.4)
            n_samples = int(duration * self.sample_rate)
            t = np.linspace(0, duration, n_samples)
            
            # Rising then cascading tone with soft vibrato
            f_center = random.uniform(3200, 3600)
            f_mod = 550 * np.sin(np.pi * np.clip(t / duration, 0, 1))
            vibrato = 60 * np.sin(2 * np.pi * 18.0 * t)
            freq = f_center + f_mod + vibrato
            
            # Smooth envelope with soft mountain echo
            env = (np.sin(np.pi * np.clip(t / duration, 0, 1)) ** 2.0)
            phase = 2 * np.pi * np.cumsum(freq) / self.sample_rate
            mono_call = np.sin(phase) * env * 0.045
        else:
            # Kōlea (Pacific Golden-Plover):
            # Pure descending soft slur (2.4 kHz -> 1.9 kHz)
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
        stereo_call = np.column_stack((mono_call * np.cos(pan_angle), mono_call * np.sin(pan_angle)))
        self.active_bird_calls.append({'audio': stereo_call, 'pos': 0})

    def generate_chunk(self, n_samples=4096):
        """Generate the next audio buffer chunk in real-time."""
        dt_chunk = n_samples * self.dt
        self.current_time += dt_chunk

        pink_chunk = self.pink_gen.generate(n_samples)
        brown_chunk = self.brown_gen.generate(n_samples)
        white_chunk = np.random.normal(0, 0.75, (n_samples, 2))

        # 1. Nearshore Wave Scheduling & Swell Sets
        self.time_to_next_wave -= dt_chunk
        if self.time_to_next_wave <= 0:
            if self.in_set:
                intensity = random.uniform(0.9, 1.35)
                self.active_waves.append(WaveEvent(self.preset, intensity=intensity))
                self.waves_spawned_in_set += 1
                if self.waves_spawned_in_set >= self.waves_in_current_set:
                    self.in_set = False
                    self.time_to_next_wave = random.uniform(14.0, 24.0)
                else:
                    self.time_to_next_wave = random.uniform(self.preset['wave_period_min'], self.preset['wave_period_max'])
            else:
                intensity = random.uniform(0.45, 0.75)
                self.active_waves.append(WaveEvent(self.preset, intensity=intensity))
                self.in_set = True
                self.waves_spawned_in_set = 0
                self.waves_in_current_set = random.randint(3, 5)
                self.time_to_next_wave = random.uniform(self.preset['wave_period_min'], self.preset['wave_period_max'])

            if random.random() < self.preset['wildlife_prob']:
                self._spawn_bird_call()

        # Sum nearshore active waves
        waves_mix = np.zeros((n_samples, 2))
        for w in self.active_waves:
            if w.active:
                waves_mix += w.step(n_samples, self.dt, pink_chunk, white_chunk)
        self.active_waves = [w for w in self.active_waves if w.active]

        # 2. Continuous Ocean Floor Swell Bed
        ocean_bed, self.zi_ocean_bed = signal.sosfilt(self.sos_ocean_bed, brown_chunk, axis=0, zi=self.zi_ocean_bed)
        ocean_bed = ocean_bed * self.preset['swell_bed_gain']

        # 3. Hawaiian Trade Winds (Ka Makani)
        self.wind_phase1 += 2 * np.pi * self.preset['wind_lfo_speed'] * dt_chunk
        self.wind_phase2 += 2 * np.pi * (self.preset['wind_lfo_speed'] * 1.618) * dt_chunk
        wind_mod = 0.70 + 0.30 * np.sin(self.wind_phase1) + 0.15 * np.cos(self.wind_phase2)
        wind_audio, self.zi_wind = signal.sosfilt(self.sos_wind, pink_chunk, axis=0, zi=self.zi_wind)
        wind_audio = wind_audio * (wind_mod * self.preset['wind_gain'])

        # 4. Distant Outer Barrier Reef Breakers (Crucial for Anini, Keʻe, North Shore)
        outer_reef_gain = self.preset.get('outer_reef_gain', 0.0)
        outer_reef_audio = np.zeros((n_samples, 2))
        if outer_reef_gain > 0.01:
            # Slow rolling swell period on the outer barrier (0.06 - 0.10 Hz)
            self.outer_reef_phase += 2 * np.pi * 0.075 * dt_chunk
            reef_swell = (0.65 + 0.35 * np.sin(self.outer_reef_phase)) ** 2.0
            raw_reef = (pink_chunk * 0.7 + brown_chunk * 0.3) * reef_swell
            outer_reef_filtered, self.zi_outer_reef = signal.sosfilt(self.sos_outer_reef, raw_reef, axis=0, zi=self.zi_outer_reef)
            outer_reef_audio = outer_reef_filtered * outer_reef_gain * 0.75

        # 5. Wildlife / Seabirds
        birds_mix = np.zeros((n_samples, 2))
        remaining_birds = []
        for bird in self.active_bird_calls:
            b_audio = bird['audio']
            b_pos = bird['pos']
            rem = len(b_audio) - b_pos
            if rem > 0:
                take = min(n_samples, rem)
                birds_mix[:take] += b_audio[b_pos : b_pos + take]
                bird['pos'] += take
                if bird['pos'] < len(b_audio):
                    remaining_birds.append(bird)
        self.active_bird_calls = remaining_birds

        # 6. Master Sum & Soft Saturation
        master = waves_mix * 0.72 + ocean_bed * 0.45 + wind_audio * 0.35 + outer_reef_audio * 0.50 + birds_mix
        master = np.tanh(master * 0.85)

        return master

# Backward compatibility alias
MauiOceanSynthesizer = HawaiianOceanSynthesizer
