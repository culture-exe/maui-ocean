import unittest
import numpy as np
from src.synth_engine import HawaiianOceanSynthesizer, FastPinkNoise, FastBrownNoise

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
        # Must contain all Maui and Kauai presets
        expected_presets = ['napili', 'makena', 'northshore', 'keawakapu',
                            'hanalei', 'polihale', 'kee', 'poipu', 'anini']
        for p in expected_presets:
            self.assertIn(p, HawaiianOceanSynthesizer.PRESETS)

        for preset_name in HawaiianOceanSynthesizer.PRESETS:
            synth = HawaiianOceanSynthesizer(preset_name=preset_name)
            for _ in range(25):
                chunk = synth.generate_chunk(4096)
                self.assertEqual(chunk.shape, (4096, 2))
                self.assertFalse(np.isnan(chunk).any())
                self.assertLessEqual(np.max(np.abs(chunk)), 1.0)

    def test_wildlife_calls(self):
        for wildlife in ['kolea', 'koae_kea', 'seabird']:
            synth = HawaiianOceanSynthesizer(preset_name='hanalei')
            synth.preset['wildlife_type'] = wildlife
            synth._spawn_bird_call()
            self.assertGreaterEqual(len(synth.active_bird_calls), 1)
            chunk = synth.generate_chunk(4096)
            self.assertEqual(chunk.shape, (4096, 2))
            self.assertFalse(np.isnan(chunk).any())

if __name__ == '__main__':
    unittest.main()
