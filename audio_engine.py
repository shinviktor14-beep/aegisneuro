import time
import struct
import numpy as np
import pyaudio

class NeuroAudioEngine:
    def __init__(self, base_freq=150.0, sample_rate=44100):
        self.base_freq = base_freq      # Базовая частота (несущая) в Гц
        self.sample_rate = sample_rate  # Частота дискретизации
        self.p = pyaudio.PyAudio()
        
        # Открываем аудиопоток (стерео, 16-бит)
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=self.sample_rate,
            output=True
        )
        
        self.is_playing = False
        self.phase_left = 0.0
        self.phase_right = 0.0

    def generate_binaural_chunk(self, target_brain_freq, chunk_size=1024):
        """
        Генерирует маленький кусочек (чанк) аудио.
        target_brain_freq: частота, в которую мы целимся (например, 10 Гц для Альфа)
        """
        # Левое ухо слышит базовую частоту, правое — смещенную
        f_left = self.base_freq
        f_right = self.base_freq + target_brain_freq

        # Создаем временную шкалу для этого чанка
        t = np.arange(chunk_size) / self.sample_rate
        
        # Вычисляем фазы, чтобы звук был плавным и без щелчков на стыках чанков
        t_left = t + self.phase_left
        t_right = t + self.phase_right
        
        # Обновляем фазы для следующего чанка
        self.phase_left += chunk_size / self.sample_rate
        self.phase_right += chunk_size / self.sample_rate

        # Генерируем чистые синусоиды
        signal_left = np.sin(2 * np.pi * f_left * t_left)
        signal_right = np.sin(2 * np.pi * f_right * t_right)

        # Объединяем в стерео-сигнал и переводим в 16-битный формат (PCM)
        stereo_signal = np.empty((chunk_size * 2,), dtype=np.int16)
        stereo_signal[0::2] = (signal_left * 16383).astype(np.int16) # Макс громкость 50% чтобы не оглохнуть
        stereo_signal[1::2] = (signal_right * 16383).astype(np.int16)

        return stereo_signal.tobytes()

    def play_session(self, duration_sec=15):
        """Запуск демонстрационной сессии с изменением частоты"""
        self.is_playing = True
        print("-> Наушники надеты? Начинаем сессию биорегуляции...")
        
        start_time = time.time()
        chunk_size = 1024
        
        try:
            while self.is_playing:
                elapsed = time.time() - start_time
                if elapsed > duration_sec:
                    break
                
                # Имитируем работу ИИ: первые 7 секунд плавно уводим мозг в Альфа (10 Гц),
                # а затем углубляем в Тета-состояние (5 Гц) для снятия мышечного спазма.
                if elapsed < 7:
                    current_target = 10.0  # Альфа-ритм (Релакс, снятие блоков)
                    state_name = "Альфа (Расслабление)"
                else:
                    current_target = 5.0   # Тета-ритм (Глубокое обезболивание)
                    state_name = "Тета (Анестезия)"
                
                print(f"[{elapsed:.1f}с] Направляем мозг в: {current_target} Гц -> Состояние: {state_name}", end="\r")
                
                # Генерируем и сразу отправляем в наушники
                data = self.generate_binaural_chunk(target_brain_freq=current_target, chunk_size=chunk_size)
                self.stream.write(data)
                
        finally:
            self.stop()

    def stop(self):
        print("\n-> Сессия завершена. Освобождаем аудио-каналы.")
        self.is_playing = False
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

if __name__ == "__main__":
    # Запуск тестовой 15-секундной сессии
    engine = NeuroAudioEngine(base_freq=150.0) # 150 Гц — приятный низкий гул
    engine.play_session(duration_sec=15)