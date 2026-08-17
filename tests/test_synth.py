import unittest
import numpy as np
from src.synth_engine import MauiOceanSynthesizer, FastPinkNoise, FastBrownNoise

class TestMauiSynthesizer(unittest.TestCase):
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
        for preset_name in MauiOceanSynthesizer.PRESETS:
            synth = MauiOceanSynthesizer(preset_name=preset_name)
            for _ in range(25):
                chunk = synth.generate_chunk(4096)
                self.assertEqual(chunk.shape, (4096, 2))
                self.assertFalse(np.isnan(chunk).any())
                self.assertLessEqual(np.max(np.abs(chunk)), 1.0)

if __name__ == '__main__':
    unittest.main()
