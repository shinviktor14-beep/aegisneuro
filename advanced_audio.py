import time
import struct
import numpy as np
import pyaudio
import pyttsx3
import threading

class AdvancedNeuroAudioEngine:
    def __init__(self, base_freq=120.0, sample_rate=44100):
        self.base_freq = base_freq
        self.sample_rate = sample_rate
        self.p = pyaudio.PyAudio()
        
        # Настройка голосового движка TTS
        self.tts_engine = pyttsx3.init()
        self.setup_voice()

        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=self.sample_rate,
            output=True
        )
        
        self.is_playing = False
        self.phase = 0.0
        self.music_volume = 1.0 # Полная громкость эмбиента по умолчанию

    def setup_voice(self):
        """Настройка приятного и медленного голоса для ИИ-гида"""
        voices = self.tts_engine.getProperty('voices')
        # Ищем русский или узбекский/английский голос в зависимости от системы
        for voice in voices:
            if "RU" in voice.id or "Russian" in voice.name:
                self.tts_engine.setProperty('voice', voice.id)
                break
        self.tts_engine.setProperty('rate', 130) # Замедляем темп до медитативного

    def speak_in_background(self, text):
        """Запуск речи ИИ в отдельном потоке, чтобы звук не прерывался"""
        def worker():
            # Плавно приглушаем фоновую музыку, чтобы расслышать ИИ
            self.music_volume = 0.3
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
            # Возвращаем громкость музыки обратно
            self.music_volume = 1.0
            
        threading.Thread(target=worker, daemon=True).start()

    def generate_ambient_space_wave(self, target_brain_freq, chunk_size=1024):
        """
        Генерирует сложную звуковую текстуру: 
        Бинауральный ритм + Низкочастотный космический эмбиент (модуляция шума)
        """
        t = np.arange(chunk_size) / self.sample_rate
        t_global = t + self.phase
        self.phase += chunk_size / self.sample_rate

        # 1. Основные терапевтические частоты (Левое и правое ухо)
        f_left = self.base_freq
        f_right = self.base_freq + target_brain_freq
        
        signal_left = np.sin(2 * np.pi * f_left * t_global)
        signal_right = np.sin(2 * np.pi * f_right * t_global)

        # 2. Добавляем «Космический эмбиент» (Низкочастотный гумус для красоты)
        # Модулируем амплитуду суб-баса (0.5 Гц), создавая эффект «дыхания космоса»
        ambient_mod = np.sin(2 * np.pi * 0.5 * t_global)
        sub_bass = np.sin(2 * np.pi * (self.base_freq / 2) * t_global) * ambient_mod

        # Смешиваем сигналы и применяем текущий уровень громкости
        mixed_left = (signal_left * 0.4 + sub_bass * 0.6) * self.music_volume
        mixed_right = (signal_right * 0.4 + sub_bass * 0.6) * self.music_volume

        # Ограничиваем амплитуду, чтобы избежать клиппинга звука
        mixed_left = np.clip(mixed_left, -1.0, 1.0)
        mixed_right = np.clip(mixed_right, -1.0, 1.0)

        # Упаковываем в 16-битный стерео PCM
        stereo_signal = np.empty((chunk_size * 2,), dtype=np.int16)
        stereo_signal[0::2] = (mixed_left * 16383).astype(np.int16)
        stereo_signal[1::2] = (mixed_right * 16383).astype(np.int16)

        return stereo_signal.tobytes()

    def play_demo_session(self):
        """Демо-сессия: Музыка подстраивается, ИИ говорит в реальном времени"""
        self.is_running = True
        start_time = time.time()
        chunk_size = 1024
        
        print("\n[Audio] Включаю космический био-эмбиент...")
        # Через 3 секунды после старта ИИ сделает первое объявление
        voice_triggered_1 = False
        voice_triggered_2 = False

        try:
            while self.is_running:
                elapsed = time.time() - start_time
                if elapsed > 15: # 15 секунд на демо
                    break

                # Имитируем падение стресса: сначала 9 Гц (Альфа), потом 5 Гц (Тета)
                current_target = 9.0 if elapsed < 8 else 5.0
                
                # ИИ включается голосом на основе этапов сессии
                if elapsed > 2.0 and not voice_triggered_1:
                    self.speak_in_background("Привет. Я активирую протокол расслабления сосудов. Просто дыши.")
                    voice_triggered_1 = True
                    
                if elapsed > 9.0 and not voice_triggered_2:
                    self.speak_in_background("Отлично, стресс падает. Перевожу систему в режим подавления боли.")
                    voice_triggered_2 = True

                # Генерируем красивую звуковую текстуру
                data = self.generate_ambient_space_wave(current_target, chunk_size)
                self.stream.write(data)
        finally:
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()

if __name__ == "__main__":
    engine = AdvancedNeuroAudioEngine()
    engine.play_demo_session()