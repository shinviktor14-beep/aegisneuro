import time

import numpy as np

from aegis_audio_engine import AegisAudioEngine


def test_headphone_check_routes_left_then_right_then_binaural():
    engine = AegisAudioEngine()
    engine.volume = 1.0
    engine.is_playing = True
    engine.start_headphone_check(4.7, 9.0)

    engine._mode_started_at = time.monotonic()
    left_only = engine._render_stereo(2048, 0.0)
    assert np.max(np.abs(left_only[:, 0])) > 0.5
    assert np.max(np.abs(left_only[:, 1])) == 0.0

    engine._mode_started_at = time.monotonic() - 4.0
    right_only = engine._render_stereo(2048, 0.0)
    assert np.max(np.abs(right_only[:, 0])) == 0.0
    assert np.max(np.abs(right_only[:, 1])) > 0.5

    engine._mode_started_at = time.monotonic() - 7.0
    binaural = engine._render_stereo(2048, 0.0)
    assert np.max(np.abs(binaural[:, 0])) > 0.5
    assert np.max(np.abs(binaural[:, 1])) > 0.5
    assert not np.allclose(binaural[:, 0], binaural[:, 1])
