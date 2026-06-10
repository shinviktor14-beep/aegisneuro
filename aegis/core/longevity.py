"""Долгосрочный тренд-анализ: 7+ дней, оценка биовозраста.

Источник: ``longevity_analytics.py`` (без изменений логики). Хранит
историю в памяти процесса — при перезапуске начинается заново, как и
исходный модуль.
"""

from __future__ import annotations

import time

import numpy as np


class LongevityTrendAnalyzer:
    MIN_DAYS = 7

    def __init__(self) -> None:
        self.history: list[dict] = []

    def log_morning_baseline(self, hr: float, rmssd: float, stress_idx: float) -> None:
        self.history.append(
            {"timestamp": time.time(), "hr": hr, "rmssd": rmssd, "stress_index": stress_idx}
        )

    def analyze_longevity_trends(self) -> dict:
        if len(self.history) < self.MIN_DAYS:
            return {
                "status": "Incomplete",
                "message": f"Необходимо собрать данные минимум за {self.MIN_DAYS} дней для выявления тренда омоложения.",
            }

        hrs = [day["hr"] for day in self.history]
        rmssds = [day["rmssd"] for day in self.history]
        stresses = [day["stress_index"] for day in self.history]

        split_size = max(1, len(self.history) // 3)
        initial_rmssd = float(np.mean(rmssds[:split_size]))
        current_rmssd = float(np.mean(rmssds[-split_size:]))
        initial_hr = float(np.mean(hrs[:split_size]))
        current_hr = float(np.mean(hrs[-split_size:]))

        rmssd_growth = ((current_rmssd - initial_rmssd) / initial_rmssd) * 100
        hr_reduction = initial_hr - current_hr

        verdict = "Стабильное состояние"
        bio_age_delta = 0.0
        if rmssd_growth > 15.0 and hr_reduction >= 3:
            verdict = "Активное омоложение и восстановление ресурсов ДНК (удлинение теломер)."
            bio_age_delta = -round((rmssd_growth * 0.1) + (hr_reduction * 0.5), 1)
        elif rmssd_growth < -10.0:
            verdict = "Внимание: истощение вегетативной системы. Иммунитет под угрозе, высокий риск скрытых воспалений."
            bio_age_delta = 2.0

        return {
            "status": "Success",
            "metrics": {
                "rmssd_change_pct": round(rmssd_growth, 1),
                "hr_drop_bpm": round(hr_reduction, 1),
                "current_avg_stress": round(float(np.mean(stresses[-split_size:])), 1),
            },
            "biological_age_impact": bio_age_delta,
            "medical_interpretation": verdict,
        }
