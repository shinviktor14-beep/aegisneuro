"""PPG: пиковый детектор по среднему красному каналу камеры.

Источник: ``aegis_ppg_processor.py`` (без изменений логики).
"""

from __future__ import annotations

from collections import deque
from datetime import datetime

import numpy as np


class AegisPPGProcessor:
    """Принимает кадры с камеры (среднее красного), отдаёт R-R интервалы в мс."""

    def __init__(self, buffer_size: int = 300) -> None:
        self.buffer_size = buffer_size
        self.red_values: deque[float] = deque(maxlen=buffer_size)
        self.timestamps: deque[float] = deque(maxlen=buffer_size)
        self.is_calibrated = False

    def process_frame(self, frame_data: float) -> None:
        self.red_values.append(frame_data)
        self.timestamps.append(datetime.now().timestamp())

    def get_rr_intervals(self) -> list[int]:
        if len(self.red_values) < 100:
            return []
        raw_signal = np.array(self.red_values, dtype=np.float32)
        times = np.array(self.timestamps, dtype=np.float32)

        window_size = 5
        if len(raw_signal) > window_size:
            smooth = np.convolve(raw_signal, np.ones(window_size) / window_size, mode="same")
        else:
            smooth = raw_signal

        trend_window = 25
        trend = np.convolve(smooth, np.ones(trend_window) / trend_window, mode="same")
        signal = smooth - trend

        adaptive_threshold = np.std(signal) * 0.4
        peaks: list[float] = []
        for i in range(1, len(signal) - 1):
            if signal[i] > signal[i - 1] and signal[i] > signal[i + 1]:
                if signal[i] > adaptive_threshold:
                    if not peaks or (times[i] - peaks[-1]) > 0.4:
                        peaks.append(times[i])

        rr_intervals: list[int] = []
        for j in range(1, len(peaks)):
            rr_ms = (peaks[j] - peaks[j - 1]) * 1000
            if 333 < rr_ms < 1500:
                rr_intervals.append(int(rr_ms))
        return rr_intervals

    def check_signal_quality(self) -> str:
        if len(self.red_values) < 15:
            return "WAITING"
        raw_signal = np.array(self.red_values)
        std_dev = float(np.std(raw_signal))
        mean_val = float(np.mean(raw_signal))
        if mean_val < 10.0:
            return "NO_FINGER"
        if std_dev < 0.3:
            return "NO_PULSE"
        return "OK"

    def reset(self) -> None:
        self.red_values.clear()
        self.timestamps.clear()
