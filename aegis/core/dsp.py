"""DSP: скользящее окно R-R интервалов, RMSSD, индекс Баевского.

Источник: ``bio_dsp.py`` (без изменений логики).
"""

from __future__ import annotations

import numpy as np


class BioSignalProcessor:
    """Хранит R-R интервалы (мс) в скользящем окне заданной длительности."""

    def __init__(self, window_size_sec: int = 120) -> None:
        self.rr_buffer: list[float] = []
        self.window_size_ms = window_size_sec * 1000

    def add_rr_interval(self, rr_ms: float) -> None:
        if rr_ms <= 0:
            return
        self.rr_buffer.append(rr_ms)
        while sum(self.rr_buffer) > self.window_size_ms:
            self.rr_buffer.pop(0)

    def calculate_rmssd(self) -> float:
        if len(self.rr_buffer) < 5:
            return 0.0
        diffs = np.diff(self.rr_buffer)
        return round(float(np.sqrt(np.mean(diffs ** 2))), 1)

    def calculate_baevsky_stress_index(self) -> float:
        if len(self.rr_buffer) < 20:
            return 100.0
        rr_array = np.array(self.rr_buffer)
        rounded = np.round(rr_array / 50) * 50
        values, counts = np.unique(rounded, return_counts=True)
        mo_index = int(np.argmax(counts))
        mo = values[mo_index] / 1000.0
        amo = (counts[mo_index] / len(rr_array)) * 100.0
        mx_d_mn = (np.max(rr_array) - np.min(rr_array)) / 1000.0
        if mx_d_mn == 0:
            mx_d_mn = 0.05
        stress = amo / (2.0 * mo * mx_d_mn)
        return round(float(stress), 1)

    def reset(self) -> None:
        self.rr_buffer.clear()
