"""Бегущий в фоне стерео-поток с горячей сменой частоты.

Источник: ``aegis_audio_engine.py`` (логика сохранена). Стартует/тушится
через ``start()``/``stop()``. Импорт ``pyaudio`` ленивый — модуль можно
импортировать в окружениях без аудио-стека.
"""

from __future__ import annotations

import threading
from typing import Optional

import numpy as np

from aegis import config


class AegisAudioEngine:
    def __init__(self) -> None:
        self.sample_rate = config.SAMPLE_RATE
        self.carrier_freq = config.CARRIER_FREQ_HZ
        self.binaural_beat = 8.0
        self.volume = 0.5

        self.is_running = False
        self.is_playing = False
        self._thread: Optional[threading.Thread] = None

        self._pyaudio = None
        self._stream = None

    def set_frequency(self, target_freq: float) -> None:
        self.binaural_beat = float(target_freq)

    def set_volume(self, v: float) -> None:
        self.volume = max(0.0, min(1.0, float(v)))

    def _open_stream(self) -> None:
        import pyaudio

        self._pyaudio = pyaudio.PyAudio()
        self._stream = self._pyaudio.open(
            format=pyaudio.paFloat32,
            channels=2,
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=config.CHUNK_SIZE,
        )

    def _close_stream(self) -> None:
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pyaudio is not None:
            self._pyaudio.terminate()
            self._pyaudio = None

    def _generate_stereo_wave(self) -> None:
        try:
            self._open_stream()
        except Exception as e:
            print(f"[Aegis-Audio] Не удалось открыть аудио-поток: {e}")
            self.is_running = False
            self.is_playing = False
            return

        start_time = 0.0
        chunk_size = config.CHUNK_SIZE
        try:
            while self.is_running:
                t = start_time + np.arange(chunk_size) / self.sample_rate
                freq_left = self.carrier_freq - (self.binaural_beat / 2.0)
                freq_right = self.carrier_freq + (self.binaural_beat / 2.0)
                wave_left = np.sin(2 * np.pi * freq_left * t)
                wave_right = np.sin(2 * np.pi * freq_right * t)
                stereo = np.empty((chunk_size, 2), dtype=np.float32)
                stereo[:, 0] = wave_left * self.volume
                stereo[:, 1] = wave_right * self.volume
                try:
                    self._stream.write(stereo.tobytes())
                except Exception:
                    break
                start_time += chunk_size / self.sample_rate
        finally:
            self._close_stream()

    def start(self) -> None:
        if self.is_playing:
            return
        self.is_running = True
        self.is_playing = True
        self._thread = threading.Thread(target=self._generate_stereo_wave, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.is_running = False
        self.is_playing = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
