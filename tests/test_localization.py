import json
import unittest
import numpy as np
from src.app import synthetic
from sound_direction.localization import Localizer, Tracker, validate


class LocalizationTests(unittest.TestCase):
    def setUp(self):
        with open('config.json') as file:
            self.cfg = json.load(file)
        self.cfg.update(angle_offset_deg=0, mirror=False)

    def test_va60x_physical_microphone_mapping(self):
        self.assertEqual(self.cfg['mic_labels'], ['MIC_1', 'MIC_2', 'MIC_4', 'MIC_5', 'MIC_6', 'MIC_8'])
        self.assertEqual(self.cfg['mic_channels'], [0, 4, 5, 1, 2, 3])
        self.assertEqual(self.cfg['channels'], 8)
        self.assertEqual(self.cfg['vad_channel'], 0)
        self.assertEqual(self.cfg['asr_channel'], 0)

    def test_full_circle_fractional_delays(self):
        loc = Localizer(self.cfg)
        for angle in range(0, 360, 15):
            result = loc.process(synthetic(self.cfg, angle, seed=angle+5))
            error = abs((result['angle']-angle+180)%360-180)
            self.assertLessEqual(error, 4, (angle, result['angle']))
            self.assertTrue(result['active'])

    def test_silence_and_uncorrelated_noise(self):
        loc = Localizer(self.cfg)
        shape = (self.cfg['frame_size'], self.cfg['channels'])
        self.assertFalse(loc.process(np.zeros(shape, dtype=np.int16))['active'])
        rng = np.random.default_rng(56)
        noise = (rng.normal(size=shape)*2000).astype(np.int16)
        self.assertFalse(loc.process(noise)['active'])

    def test_unused_channel_does_not_change_direction(self):
        loc = Localizer(self.cfg)
        pcm = synthetic(self.cfg, 80)
        original = loc.process(pcm)['angle']
        pcm[:, 6] = np.random.default_rng(10).integers(-32000, 32000, self.cfg['frame_size'])
        pcm[:, 7] = np.random.default_rng(11).integers(-32000, 32000, self.cfg['frame_size'])
        self.assertEqual(original, loc.process(pcm)['angle'])

    def test_wrap_and_hold(self):
        tracker = Tracker(0.5)
        tracker.update({'active': True, 'angle': 358}, 1)
        angle, active = tracker.update({'active': True, 'angle': 2}, 1.1)
        self.assertTrue(angle > 350 or angle < 10)
        self.assertTrue(active)
        self.assertTrue(tracker.update({'active': False}, 1.3)[1])
        self.assertFalse(tracker.update({'active': False}, 2)[1])

    def test_isolated_interference_does_not_rotate_arrow(self):
        tracker = Tracker(0.55)
        tracker.update({'active': True, 'angle': 60}, 1)
        self.assertEqual(tracker.update({'active': True, 'angle': 240}, 1.04)[0], 60)
        self.assertEqual(tracker.update({'active': True, 'angle': 60}, 1.08)[0], 60)
        tracker.update({'active': True, 'angle': 180}, 1.12)
        tracker.update({'active': True, 'angle': 182}, 1.16)
        self.assertEqual(tracker.update({'active': True, 'angle': 180}, 1.20)[0], 180)
        self.assertEqual(tracker.update({'active': True, 'angle': 300}, 2)[0], 300)

    def test_calibration(self):
        self.cfg.update(mirror=True, angle_offset_deg=40)
        result = Localizer(self.cfg).process(synthetic(self.cfg, 90))
        self.assertLessEqual(abs(result['angle']-310), 4)

    def test_reject_duplicate_microphone_channel(self):
        self.cfg['mic_channels'] = [0, 4, 5, 1, 2, 2]
        with self.assertRaises(ValueError):
            validate(self.cfg)

    def test_reject_invalid_relaxed_handoff_settings(self):
        for key, value in (
            ('live_direction_handoff_relaxed_consistency', 0.9),
            ('live_direction_handoff_old_evidence_window_seconds', 0.6),
            ('live_direction_handoff_old_evidence_max_frames', -1),
            ('live_direction_handoff_old_evidence_max_frames', True),
        ):
            with self.subTest(key=key, value=value):
                cfg = dict(self.cfg)
                cfg[key] = value
                with self.assertRaises(ValueError):
                    validate(cfg)

    def test_below_manual_gate_still_estimates_reliable_direction(self):
        self.cfg['gate_dbfs'] = -20
        result = Localizer(self.cfg).process(synthetic(self.cfg, 60, amplitude=0.01))
        self.assertLess(result['dbfs'], self.cfg['gate_dbfs'])
        self.assertFalse(result['active'])
        self.assertTrue(result['direction_valid'])
        self.assertLess(abs(result['angle']-60), 4)

    def test_learned_stationary_tone_is_downweighted_without_losing_speech_direction(self):
        loc = Localizer(self.cfg)
        u = np.array([np.sin(np.deg2rad(240)), np.cos(np.deg2rad(240))])
        delays = -loc.positions@u/343
        def hum(block):
            t = (np.arange(self.cfg['frame_size'])+block*self.cfg['frame_size'])/self.cfg['rate']
            noise = np.zeros((self.cfg['frame_size'], self.cfg['channels']))
            for i, delay in enumerate(delays):
                noise[:, self.cfg['mic_channels'][i]] = 0.2*np.sin(2*np.pi*850*(t-delay))
            return (noise*32768).astype(np.int16)
        for block in range(30):
            loc.process(hum(block), learn_noise=True)
        speech = synthetic(self.cfg, 60, seed=3, amplitude=0.015)
        mixed = np.clip(hum(31).astype(int)+speech.astype(int), -32768, 32767).astype(np.int16)
        result = loc.process(mixed, suppress_noise=True)
        self.assertTrue(result['direction_valid'])
        self.assertLess(abs(result['angle']-60), 4)
        self.assertLess(result['analysis_dbfs'], result['dbfs']-10)


if __name__ == '__main__':
    unittest.main()
