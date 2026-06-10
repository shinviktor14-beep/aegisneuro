"""AegisAudioEngine — бинауральный тон для закрытого нейро-контура.

Платформы:
  - Android:  android.media.AudioTrack через pyjnius (STREAM_MUSIC, float PCM).
  - Десктоп:  pyaudio, если доступен; иначе no-op (тон не слышен, но
              set_frequency/start_tone/stop_tone не падают, чтобы UI работал).

Публичный API (НЕ меняется, чтобы остальные модули не переписывать):
  - set_frequency(target_freq: float)
  - start_tone()
  - stop_tone()
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np

try:
    from kivy.utils import platform as _kivy_platform
    IS_ANDROID = (_kivy_platform == "android")
except Exception:  # noqa: BLE001
    IS_ANDROID = False


class AegisAudioEngine:
    def __init__(self) -> None:
        self.sample_rate = 44100
        self.carrier_freq = 200.0
        self.binaural_beat = 8.0
        self.volume = 0.5

        self.is_playing = False
        self.is_running = False
        self.thread: Optional[threading.Thread] = None

        # Android-специфичное
        self._audio_track = None
        # Десктоп-специфичное
        self._p = None
        self._stream = None

    # -------------------------------------------------------- публичный API
    def set_frequency(self, target_freq: float) -> None:
        """Динамическое изменение терапевтической частоты ИИ прямо во время звучания."""
        self.binaural_beat = float(target_freq)
        print(f"[Aegis-Audio] Частота бинаурального стимула перестроена на: {self.binaural_beat} Гц")

    def start_tone(self) -> None:
        if self.is_playing:
            return
        self.is_running = True
        self.is_playing = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print("[Aegis-Audio] Биорезонансный аудио-контур запущен.")

    def stop_tone(self) -> None:
        self.is_running = False
        self.is_playing = False
        time.sleep(0.05)
        if self.thread is not None:
            self.thread.join(timeout=1.0)
            self.thread = None
        self._close_native()
        print("[Aegis-Audio] Звуковой поток отключен.")

    # -------------------------------------------------------- внутреннее
    def _loop(self) -> None:
        if IS_ANDROID:
            self._loop_android()
        else:
            self._loop_desktop()

    # ......................................................... Android
    def _open_android_track(self) -> bool:
        try:
            from jnius import autoclass  # type: ignore
            AudioManager = autoclass("android.media.AudioManager")
            AudioFormat = autoclass("android.media.AudioFormat")
            AudioTrack = autoclass("android.media.AudioTrack")

            channel_mask = (
                AudioFormat.CHANNEL_OUT_FRONT_LEFT
                | AudioFormat.CHANNEL_OUT_FRONT_RIGHT
            )
            encoding = AudioFormat.ENCODING_PCM_FLOAT

            buffer_size_bytes = int(self.sample_rate * 0.1) * 2 * 4  # 100 мс, 2 канала, float32
            self._audio_track = AudioTrack(
                AudioManager.STREAM_MUSIC,
                self.sample_rate,
                channel_mask,
                encoding,
                buffer_size_bytes,
                AudioTrack.MODE_STREAM,
            )
            if self._audio_track.getState() != AudioTrack.STATE_INITIALIZED:
                print("[Aegis-Audio] AudioTrack not initialized")
                return False
            self._audio_track.play()
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[Aegis-Audio] open_android_track: {exc}")
            return False

    def _close_native(self) -> None:
        try:
            if self._audio_track is not None:
                self._audio_track.stop()
                self._audio_track.release()
                self._audio_track = None
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None
        except Exception:  # noqa: BLE001
            pass
        if self._p is not None:
            try:
                self._p.terminate()
            except Exception:  # noqa: BLE001
                pass
            self._p = None

    def _loop_android(self) -> None:
        if not self._open_android_track():
            return
        chunk_size = 1024
        start_time = 0.0
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
                self._audio_track.write(
                    stereo.tobytes(),
                    stereo.shape[0] * 2 * 4,  # frames * channels * sizeof(float32)
                    self._audio_track.WRITE_BLOCKING,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[Aegis-Audio] write: {exc}")
                break
            start_time += chunk_size / self.sample_rate
        self._close_native()

    # ......................................................... Desktop
    def _loop_desktop(self) -> None:
        try:
            import pyaudio  # type: ignore
        except Exception:  # noqa: BLE001
            print("[Aegis-Audio] pyaudio недоступен; тон на десктопе не воспроизводится.")
            # Просто «спим», чтобы set_frequency не упал
            while self.is_running:
                time.sleep(0.1)
            return

        try:
            self._p = pyaudio.PyAudio()
            self._stream = self._p.open(
                format=pyaudio.paFloat32,
                channels=2,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=1024,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[Aegis-Audio] pyaudio open: {exc}")
            return

        chunk_size = 1024
        start_time = 0.0
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
            except Exception:  # noqa: BLE001
                break
            start_time += chunk_size / self.sample_rate
        self._close_native()
