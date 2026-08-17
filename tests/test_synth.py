#!/usr/bin/env python3
import unittest
import numpy as np
from src.synth_engine import HawaiianOceanSynthesizer, FastPinkNoise, FastBrownNoise, RainGenerator, NightFaunaGenerator
from src.live_data import fetch_live_telemetry, compute_dsp_multipliers, determine_circadian_phase

class TestHawaiianSynthesizer(unittest.TestCase):
    def test_fast_noise_generators(self):
        pink = FastPinkNoise(channels=2)
        chunk_p = pink.generate(4096)
        self.assertEqual(chunk_p.shape, (4096, 2))
        self.assertFalse(np.isnan(chunk_p).any())

        brown = FastBrownNoise(channels=2)
        chunk_b = brown.generate(4096)
        self.assertEqual(chunk_b.shape, (4096, 2))
        self.assertFalse(np.isnan(chunk_b).any())

    def test_all_presets_generate_clean_audio(self):
        # Must contain all Maui and Kauai presets including new ones
        expected_presets = [
            'napili', 'makena', 'northshore', 'keawakapu',
            'honolua', 'waianapanapa', 'la-perouse', 'molokini',
            'hanalei', 'polihale', 'kee', 'poipu', 'anini'
        ]
        for p in expected_presets:
            self.assertIn(p, HawaiianOceanSynthesizer.PRESETS)

        for preset_name in HawaiianOceanSynthesizer.PRESETS:
            synth = HawaiianOceanSynthesizer(preset_name=preset_name, enable_live=False, circadian_mode='off')
            for _ in range(15):
                chunk = synth.generate_chunk(4096)
                self.assertEqual(chunk.shape, (4096, 2))
                self.assertFalse(np.isnan(chunk).any())
                self.assertLessEqual(np.max(np.abs(chunk)), 1.0)

    def test_rain_generator(self):
        rain = RainGenerator(sample_rate=48000)
        rain.set_intensity(0.8)
        pink = np.random.normal(0, 0.5, (4096, 2))
        white = np.random.normal(0, 0.5, (4096, 2))
        brown = np.random.normal(0, 0.5, (4096, 2))
        out = rain.generate(4096, pink, white, brown)
        self.assertEqual(out.shape, (4096, 2))
        self.assertFalse(np.isnan(out).any())

    def test_night_fauna_generator(self):
        night = NightFaunaGenerator(sample_rate=48000)
        night.set_night_blend(1.0)
        out = night.generate(4096)
        self.assertEqual(out.shape, (4096, 2))
        self.assertFalse(np.isnan(out).any())

    def test_circadian_phases(self):
        for phase in ['dawn', 'day', 'sunset', 'night', 'auto']:
            synth = HawaiianOceanSynthesizer(preset_name='honolua', enable_live=False, circadian_mode=phase)
            chunk = synth.generate_chunk(4096)
            self.assertEqual(chunk.shape, (4096, 2))
            self.assertFalse(np.isnan(chunk).any())

    def test_live_telemetry_computation(self):
        sample_telem = {
            'wave_height_m': 2.2,
            'wave_period_s': 14.0,
            'wind_speed_kmh': 25.0,
            'precipitation_mm': 2.5
        }
        mults = compute_dsp_multipliers(sample_telem)
        self.assertIn('swell_gain_mult', mults)
        self.assertIn('wave_period_mult', mults)
        self.assertIn('wind_gain_mult', mults)
        self.assertIn('rain_intensity', mults)
        self.assertGreater(mults['rain_intensity'], 0.0)

    def test_wildlife_calls(self):
        for wildlife in ['kolea', 'koae_kea', 'seabird']:
            synth = HawaiianOceanSynthesizer(preset_name='honolua', enable_live=False)
            synth.preset['wildlife_type'] = wildlife
            synth._spawn_bird_call()
            self.assertGreaterEqual(len(synth.active_bird_calls), 1)
            chunk = synth.generate_chunk(4096)
            self.assertEqual(chunk.shape, (4096, 2))
            self.assertFalse(np.isnan(chunk).any())

if __name__ == '__main__':
    unittest.main()
