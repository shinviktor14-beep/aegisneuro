import logging

import numpy as np
import pyaudio
import math

log = logging.getLogger(__name__)

class AegisSpatialAudioEngine:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate
        self.p = pyaudio.PyAudio()
        
        # Открываем стерео-поток (2 канала)
        self.stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=2,
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=1024
        )
        
        # Текущий угол источника звука вокруг головы (в радианах)
        self.current_angle = 0.0 
        log.info("Пространственный HRTF-движок успешно инициализирован.")

    def generate_spatial_chunk(self, target_brain_freq, base_freq=150.0, chunk_size=1024, rotation_speed=0.02):
        """
        Генерация куска аудио (chunk) с динамическим вращением 
        терапевтической бинауральной волны вокруг головы на 360 градусов.
        """
        t = np.arange(chunk_size) / self.sample_rate
        
        # 1. Генерируем базовые несущие частоты для бинаурального эффекта
        # Левое ухо получает базовую частоту, правое - смещенную на частоту работы мозга (например, Альфа = +10 Гц)
        wave_left_raw = np.sin(2 * np.pi * base_freq * t)
        wave_right_raw = np.sin(2 * np.pi * (base_freq + target_brain_freq) * t)
        
        # 2. Вычисляем физику пространственного положения (Угол theta)
        self.current_angle = (self.current_angle + rotation_speed) % (2 * np.pi)
        
        # Математика ILD (Интернауральная разность интенсивностей)
        # Вычисляем, насколько звук тише/громче в каждом ухе в зависимости от угла
        # sin(angle) = 1 (звук строго справа), sin(angle) = -1 (звук строго слева)
        pos_factor = np.sin(self.current_angle)
        
        # Коэффициенты громкости для левого и правого уха (плавное 3D-перетекание)
        vol_left = 0.5 * (1.0 - 0.5 * pos_factor)
        vol_top_right = 0.5 * (1.0 + 0.5 * pos_factor)
        
        # 3. Моделируем ITD (Интернауральная задержка времени) упрощенным фазовым сдвигом
        # Физическая задержка между ушами вокруг черепа составляет максимум ~0.65 миллисекунд
        max_phase_shift = 0.00065 # сек
        current_shift = max_phase_shift * np.cos(self.current_angle)
        
        # Применяем фазовый сдвиг к правому каналу для создания эффекта глубины «впереди/сзади»
        wave_right_spatial = np.sin(2 * np.pi * (base_freq + target_brain_freq) * (t - current_shift))
        wave_left_spatial = wave_left_raw * vol_left
        wave_right_spatial = wave_right_spatial * vol_top_right
        
        # Упаковываем каналы в один стерео-массив
        stereo_chunk = np.empty((chunk_size * 2,), dtype=np.float32)
        stereo_chunk[0::2] = wave_left_spatial  # Левый канал
        stereo_chunk[1::2] = wave_right_spatial # Правый канал
        
        # Применяем легкое эмбиент-размытие, имитируя отражение звука от плеч
        stereo_chunk = np.clip(stereo_chunk, -1.0, 1.0)
        
        return stereo_chunk.tobytes()

    def play_test_session(self, duration_sec=10, target_brain_freq=7.83):
        """Тестовый запуск пространственного вращения частоты резонанса Шумана"""
        log.info(f"ТЕСТ 3D-ЗВУКА AEGISNEURO ({target_brain_freq} Гц)")
        log.info("НАДЕНЬТЕ НАУШНИКИ! Вы должны почувствовать, как космический эмбиент плавно летает вокруг головы.")
        
        chunks_needed = int(duration_sec * self.sample_rate / 1024)
        
        # Изменяем скорость вращения: ИИ делает волну более «тягучей»
        for _ in range(chunks_needed):
            # Генерируем 3D-звук
            chunk = self.generate_spatial_chunk(
                target_brain_freq=target_brain_freq, 
                base_freq=120.0, 
                chunk_size=1024,
                rotation_speed=0.015 # Скорость полета звука
            )
            self.stream.write(chunk)
            
        self.close()

    def close(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        log.info("Аудиопоток успешно остановлен.")

if __name__ == "__main__":
    # Запуск 10-секундного теста. Частота 7.83 Гц (глубокая релаксация и медитация)
    engine = AegisSpatialAudioEngine()
    engine.play_test_session(duration_sec=10, target_brain_freq=7.83)