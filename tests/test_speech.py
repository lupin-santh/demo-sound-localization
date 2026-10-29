import json
import unittest
import numpy as np
from src.app import synthetic
from sound_direction.speech import SpeechDetector, ArraySpeechDetector, Pipeline


class FakeVAD:
    def __init__(self, positives):
        self.positives = iter(positives)
        self.frames = []

    def set_mode(self, mode):
        self.mode = mode

    def is_speech(self, frame, rate):
        assert len(frame) == rate*20//1000*2 and rate == 16000
        self.frames.append(frame)
        return next(self.positives)


class SpeechTests(unittest.TestCase):
    def setUp(self):
        with open('config.json') as file:
            self.cfg = json.load(file)
        self.cfg.update(vad_enabled=True, asr_enabled=False, vad_mode=2, gate_dbfs=-43)

    def test_stream_alignment_and_channel(self):
        fake = FakeVAD([False]*30)
        detector = SpeechDetector(self.cfg, fake)
        stream = np.arange(self.cfg['frame_size']*4*self.cfg['channels'], dtype=np.int16).reshape(-1, self.cfg['channels'])
        for block in np.split(stream, 4):
            detector.process(block)
        consumed = b''.join(fake.frames)
        vad_samples = self.cfg['rate']*20//1000
        consumed_samples = len(stream)//vad_samples*vad_samples
        expected = stream[:consumed_samples, 0].astype('<i2').tobytes()
        self.assertEqual(consumed, expected)
        self.assertEqual(bytes(detector.buffer), stream[consumed_samples:, 0].astype('<i2').tobytes())

    def test_onset_and_release(self):
        detector = SpeechDetector(self.cfg, FakeVAD([True, True]+[False]*8))
        one = np.zeros((self.cfg['rate']*20//1000, self.cfg['channels']), dtype=np.int16)
        self.assertFalse(detector.process(one)['speech'])
        self.assertTrue(detector.process(one)['speech'])
        for _ in range(7):
            self.assertTrue(detector.process(one)['speech'])
        self.assertFalse(detector.process(one)['speech'])

    def test_voice_gate_keeps_direction_but_rejects_animation(self):
        self.cfg['vad_enabled'] = False
        pipeline = Pipeline(self.cfg)
        pcm = synthetic(self.cfg, 80)
        sound = pipeline.process(pcm)
        self.assertTrue(sound['active'])
        self.cfg['vad_enabled'] = True
        pipeline.detector = SpeechDetector(self.cfg, FakeVAD([False]*10))
        voice = pipeline.process(pcm)
        self.assertEqual(sound['angle'], voice['angle'])
        self.assertFalse(voice['active'])
        self.assertFalse(voice['speech'])

    def test_real_engine_silence(self):
        try:
            import webrtcvad
        except ImportError:
            self.skipTest('WebRTC VAD dependency unavailable')
        detector = SpeechDetector(self.cfg)
        for _ in range(30):
            result = detector.process(np.zeros((self.cfg['frame_size'], self.cfg['channels']), dtype=np.int16))
            self.assertFalse(result['speech'])

    def test_asr_keeps_speech_when_localization_gate_rejects_sound(self):
        self.cfg.update(vad_enabled=False, asr_enabled=False, gate_dbfs=-5)
        pipeline = Pipeline(self.cfg)
        self.cfg['asr_enabled'] = True
        pipeline.detector = SpeechDetector(self.cfg, FakeVAD([True]*10))
        pipeline.process(synthetic(self.cfg, 80))
        result = pipeline.process(synthetic(self.cfg, 80))
        self.assertFalse(result['active'])
        self.assertTrue(result['speech'])
        self.assertEqual(result['speech_ratio'], 1.0)
        self.assertIn('gate_dbfs', result['sentence_direction_rejections'])

    def test_quiet_speech_can_transcribe_but_has_no_sentence_direction(self):
        self.cfg.update(vad_enabled=False, gate_dbfs=-20)
        pipeline = Pipeline(self.cfg)
        self.cfg['vad_enabled'] = True
        pipeline.detector = SpeechDetector(self.cfg, FakeVAD([True]*10))
        pipeline.process(synthetic(self.cfg, 60, amplitude=0.01))
        result = pipeline.process(synthetic(self.cfg, 60, amplitude=0.01))
        self.assertLess(result['dbfs'], self.cfg['gate_dbfs'])
        self.assertTrue(result['active'])
        self.assertFalse(result['sentence_direction_valid'])
        self.assertEqual(result['sentence_direction_rejections'], ('gate_dbfs',))
        self.assertLess(abs(result['angle']-60), 4)

    def test_speech_above_base_gate_can_supply_sentence_direction(self):
        self.cfg.update(vad_enabled=False, gate_dbfs=-45)
        pipeline = Pipeline(self.cfg)
        self.cfg['vad_enabled'] = True
        pipeline.detector = SpeechDetector(self.cfg, FakeVAD([True]*10))
        pipeline.process(synthetic(self.cfg, 60))
        result = pipeline.process(synthetic(self.cfg, 60))
        self.assertGreaterEqual(result['dbfs'], self.cfg['gate_dbfs'])
        self.assertTrue(result['sentence_direction_valid'])
        self.assertEqual(result['sentence_direction_rejections'], ())

    def test_non_speech_does_not_get_human_gate_bypass(self):
        self.cfg.update(vad_enabled=False, gate_dbfs=-20)
        pipeline = Pipeline(self.cfg)
        self.cfg['vad_enabled'] = True
        pipeline.detector = SpeechDetector(self.cfg, FakeVAD([False]*10))
        result = pipeline.process(synthetic(self.cfg, 60, amplitude=0.01))
        self.assertFalse(result['active'])
        self.assertFalse(result['sentence_direction_valid'])

    def test_one_false_positive_microphone_does_not_trigger_speech(self):
        array = object.__new__(ArraySpeechDetector)
        array.cfg = self.cfg
        class Detector:
            def __init__(self, speech):
                self.cfg = {}
                self.speech = speech
            def process(self, pcm):
                return {'speech': self.speech, 'speech_ratio': float(self.speech)}
        array.detectors = [Detector(True), Detector(False), Detector(False)]
        shape = (self.cfg['frame_size'], self.cfg['channels'])
        self.assertFalse(array.process(np.zeros(shape, dtype=np.int16))['speech'])
        array.detectors = [Detector(True), Detector(False), Detector(True)]
        self.assertTrue(array.process(np.zeros(shape, dtype=np.int16))['speech'])


if __name__ == '__main__':
    unittest.main()
