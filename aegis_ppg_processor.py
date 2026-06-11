import logging

import numpy as np
from datetime import datetime
from collections import deque

log = logging.getLogger(__name__)

class AegisPPGProcessor:
    def __init__(self):
        self.buffer_size = 300  # Около 10 сек при 30fps
        # Использование deque вместо list исключает просадки FPS при очистке буфера
        self.red_values = deque(maxlen=self.buffer_size)
        self.timestamps = deque(maxlen=self.buffer_size)
        self.is_calibrated = False

    def process_frame(self, frame_data):
        """
        Принимает средний уровень красного цвета из кадра камеры.
        frame_data: среднее значение интенсивности красного (float)
        """
        current_time = datetime.now().timestamp()
        self.red_values.append(frame_data)
        self.timestamps.append(current_time)

    def get_rr_intervals(self):
        """
        Математический поиск пиков (ударов сердца) в потоке данных.
        Возвращает массив R-R интервалов в миллисекундах.
        """
        if len(self.red_values) < 100:
            return []

        # Превращаем в numpy массивы для быстрой математики
        raw_signal = np.array(self.red_values, dtype=np.float32)
        times = np.array(self.timestamps, dtype=np.float32)

        # 1. Сглаживание высокочастотного шума матрицы камеры (Moving Average фильтр)
        # Окно в 5 кадров (~160 мс) сгладит «дребезг», но сохранит форму пульсовой волны
        window_size = 5
        if len(raw_signal) > window_size:
            smooth_signal = np.convolve(raw_signal, np.ones(window_size)/window_size, mode='same')
        else:
            smooth_signal = raw_signal

        # 2. Удаление низкочастотного тренда (дрейфа изолинии от дыхания/нажема)
        # Вычитаем локальное среднее, чтобы сигнал колебался строго вокруг нуля
        trend_window = 25  # Около 800 мс (средняя длина кардиоцикла)
        trend = np.convolve(smooth_signal, np.ones(trend_window)/trend_window, mode='same')
        signal = smooth_signal - trend

        # 3. Поиск реальных пиков с адаптивной фильтрацией шума
        peaks = []
        # Динамический порог: пик должен быть выше, чем 40% от стандартного отклонения сигнала
        adaptive_threshold = np.std(signal) * 0.4
        
        for i in range(1, len(signal) - 1):
            # Условие 1: Локальный максимум
            if signal[i] > signal[i-1] and signal[i] > signal[i+1]:
                # Условие 2: Амплитуда выше адаптивного порога (отсекаем мелкий шум)
                if signal[i] > adaptive_threshold:
                    # Условие 3: Защита от спаренных пиков (минимальное время между ударами 400 мс)
                    if len(peaks) == 0 or (times[i] - peaks[-1]) > 0.4:
                        peaks.append(times[i])

        # 4. Расчет R-R интервалов
        rr_intervals = []
        if len(peaks) > 1:
            for j in range(1, len(peaks)):
                rr_ms = (peaks[j] - peaks[j-1]) * 1000
                # Фильтр физиологических артефактов (нормальный пульс человека: 40 - 180 уд/мин)
                if 333 < rr_ms < 1500:
                    rr_intervals.append(int(rr_ms))
        
        return rr_intervals

    def check_signal_quality(self):
        """Проверяет, приложен ли палец (сигнал должен быть стабильным и пульсирующим)"""
        if len(self.red_values) < 15: 
            return "WAITING"
            
        raw_signal = np.array(self.red_values)
        std_dev = np.std(raw_signal)
        mean_val = np.mean(raw_signal)
        
        # 1. Если палец убрали, камера поймает комнатный свет, средняя яркость упадет,
        # а шум матрицы создаст ложную микро-вариативность.
        if mean_val < 10.0: 
            return "NO_FINGER"
            
        # 2. Если палец лежит неподвижно без вспышки или это статичная картинка
        if std_dev < 0.3: 
            return "NO_PULSE"
            
        return "OK"