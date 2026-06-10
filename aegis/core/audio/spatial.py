"""Пространственный HRTF: вращение бинаурального источника вокруг головы.

Источник: ``aegis_spatial_audio.py`` (логика ILD + ITD сохранена). Импорт
``pyaudio`` ленивый.
"""

from __future__ import annotations

import math

import numpy as np

from aegis import config


class SpatialAudioEngine:
    def __init__(self) -> None:
        self.sample_rate = config.SAMPLE_RATE
        self.current_angle = 0.0
        self._pyaudio = None
        self._stream = None

    def generate_spatial_chunk(
        self,
        target_brain_freq: float,
        base_freq: float = 150.0,
        chunk_size: int = config.CHUNK_SIZE,
        rotation_speed: float = 0.02,
    ) -> bytes:
        t = np.arange(chunk_size) / self.sample_rate
        wave_left_raw = np.sin(2 * math.pi * base_freq * t)
        wave_right_raw = np.sin(2 * math.pi * (base_freq + target_brain_freq) * t)

        self.current_angle = (self.current_angle + rotation_speed) % (2 * math.pi)
        pos_factor = math.sin(self.current_angle)
        vol_left = 0.5 * (1.0 - 0.5 * pos_factor)
        vol_right = 0.5 * (1.0 + 0.5 * pos_factor)

        max_phase_shift = 0.00065
        current_shift = max_phase_shift * math.cos(self.current_angle)
        wave_right_spatial = np.sin(
            2 * math.pi * (base_freq + target_brain_freq) * (t - current_shift)
        )
        wave_left_spatial = wave_left_raw * vol_left
        wave_right_spatial = wave_right_spatial * vol_right

        stereo = np.empty((chunk_size * 2,), dtype=np.float32)
        stereo[0::2] = wave_left_spatial
        stereo[1::2] = wave_right_spatial
        return np.clip(stereo, -1.0, 1.0).tobytes()

    def open(self) -> None:
        import pyaudio

        self._pyaudio = pyaudio.PyAudio()
        self._stream = self._pyaudio.open(
            format=pyaudio.paFloat32,
            channels=2,
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=config.CHUNK_SIZE,
        )

    def write(self, chunk_bytes: bytes) -> None:
        if self._stream is not None:
            self._stream.write(chunk_bytes)

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pyaudio is not None:
            self._pyaudio.terminate()
            self._pyaudio = None
