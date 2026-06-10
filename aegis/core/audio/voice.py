"""Голосовой гид: TTS-фразы в фоне с приглушением фоновой музыки.

Источник: ``advanced_audio.py::AdvancedNeuroAudioEngine.speak_in_background``
(логика ducking сохранена). Импорт ``pyttsx3`` ленивый.
"""

from __future__ import annotations

import threading


class VoiceGuide:
    def __init__(self, music_volume_ref: list[float] | None = None) -> None:
        self._tts = None
        self._init_lock = threading.Lock()
        self._initialized = False
        self.music_volume_ref = music_volume_ref

    def _ensure_engine(self) -> bool:
        if self._initialized:
            return True
        with self._init_lock:
            if self._initialized:
                return True
            try:
                import pyttsx3
            except ImportError:
                return False
            try:
                self._tts = pyttsx3.init()
                voices = self._tts.getProperty("voices")
                for v in voices:
                    if "RU" in v.id or "Russian" in v.name:
                        self._tts.setProperty("voice", v.id)
                        break
                self._tts.setProperty("rate", 130)
                self._initialized = True
                return True
            except Exception:
                return False

    def speak(self, text: str) -> None:
        if not self._ensure_engine():
            return

        def _run() -> None:
            prev_volume: float | None = None
            if self.music_volume_ref is not None:
                prev_volume = self.music_volume_ref[0]
                self.music_volume_ref[0] = 0.3
            try:
                self._tts.say(text)
                self._tts.runAndWait()
            finally:
                if self.music_volume_ref is not None and prev_volume is not None:
                    self.music_volume_ref[0] = prev_volume

        threading.Thread(target=_run, daemon=True).start()
