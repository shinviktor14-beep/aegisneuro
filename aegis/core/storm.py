"""Предиктор шторма: падение RMSSD, скачок стресса, микро-альтернации.

Источник: инлайн-предиктор из ``main.py`` (адаптирован под 15-секундный
экспресс-замер; пороги ``>20%`` падения RMSSD и ``>0.12`` коэффициента
альтернаций). Бейзлайн хранится в ``data/historical_baseline.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from aegis import config


class StormPredictor:
    def __init__(self, baseline_path: Path = config.BASELINE_PATH) -> None:
        self.baseline_path = baseline_path
        self.baseline = {"avg_rmssd": 35.0, "avg_stress_idx": 120.0}
        self.load_baseline()

    def load_baseline(self) -> None:
        if self.baseline_path.exists():
            with open(self.baseline_path, "r", encoding="utf-8") as f:
                self.baseline = json.load(f)

    def save_baseline(self) -> None:
        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.baseline_path, "w", encoding="utf-8") as f:
            json.dump(self.baseline, f, ensure_ascii=False)

    def update_baseline_live(self, new_rmssd: float, new_stress: float) -> None:
        # EMA с весом 0.1 для нового замера
        self.baseline["avg_rmssd"] = float(self.baseline["avg_rmssd"] * 0.9 + new_rmssd * 0.1)
        self.baseline["avg_stress_idx"] = float(
            self.baseline["avg_stress_idx"] * 0.9 + new_stress * 0.1
        )
        self.save_baseline()

    def analyze(self, rr_intervals: list[int]) -> dict:
        if len(rr_intervals) < 10:
            return {
                "status": "INSUFFICIENT_DATA",
                "storm_probability_pct": 0,
                "triggers": ["Недостаточно пульсовых волн"],
            }

        rr_array = np.array(rr_intervals, dtype=float)
        rr_diff = np.diff(rr_array)
        current_rmssd = float(np.sqrt(np.mean(rr_diff ** 2)))

        amo = self._calculate_amplitude_of_mode(rr_intervals)
        mx_dmn = (float(np.max(rr_array)) - float(np.min(rr_array))) / 1000.0
        if mx_dmn == 0:
            mx_dmn = 0.05
        current_stress_idx = amo / (2.0 * mx_dmn * (float(np.median(rr_array)) / 1000.0))

        chunks = np.array_split(rr_array, 3)
        chunk_rmssds: list[float] = []
        for ch in chunks:
            if len(ch) > 1:
                chunk_rmssds.append(float(np.sqrt(np.mean(np.diff(ch) ** 2))))
        rmssd_alternation_coef = (
            float(np.std(chunk_rmssds) / np.mean(chunk_rmssds)) if chunk_rmssds else 0.0
        )

        storm_score = 0
        reasons: list[str] = []

        rmssd_drop_pct = (
            (self.baseline["avg_rmssd"] - current_rmssd) / self.baseline["avg_rmssd"]
        ) * 100
        if rmssd_drop_pct > 20:
            storm_score += 40
            reasons.append(f"Падение тонуса Vagus на {int(rmssd_drop_pct)}% ниже нормы")

        if current_stress_idx > self.baseline["avg_stress_idx"] * 1.5:
            storm_score += 30
            reasons.append("Скрытая гиперсимпатикотония (тревога ЦНС)")

        if rmssd_alternation_coef > 0.12:
            storm_score += 30
            reasons.append("Хаотические микро-альтернации капиллярной волны")

        storm_probability = int(min(max(storm_score, 0), 100))
        if storm_probability >= 70:
            status = "STORM_ALERT"
        elif 40 <= storm_probability < 70:
            status = "WARNING"
        else:
            status = "CLEAR"

        if status == "CLEAR":
            self.update_baseline_live(current_rmssd, current_stress_idx)

        return {
            "status": status,
            "storm_probability_pct": storm_probability,
            "metrics": {
                "rmssd": round(current_rmssd, 1),
                "stress_index": int(current_stress_idx),
                "alternation_index": round(rmssd_alternation_coef, 3),
            },
            "triggers": reasons,
            "prediction_window": "2-3 часа",
        }

    def _calculate_amplitude_of_mode(self, rr_intervals: list[int]) -> float:
        counts, _ = np.histogram(rr_intervals, bins=10)
        max_idx = int(np.argmax(counts))
        return (counts[max_idx] / len(rr_intervals)) * 100
