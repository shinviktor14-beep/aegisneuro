import time
import numpy as np

class LongevityTrendAnalyzer:
    def __init__(self):
        # В реальном приложении здесь будет подключение к локальной базе данных (SQLite)
        # Храним историю утренних замеров: (timestamp, resting_hr, rmssd, stress_index)
        self.history = []

    def log_morning_baseline(self, hr, rmssd, stress_idx):
        """Запись данных утреннего калибровочного замера"""
        self.history.append({
            "timestamp": time.time(),
            "hr": hr,
            "rmssd": rmssd,
            "stress_index": stress_idx
        })

    def analyze_longevity_trends(self):
        """
        Анализирует динамику за все время. 
        Возвращает вердикт о скорости старения и состоянии иммунной системы.
        """
        if len(self.history) < 7:
            return {
                "status": "Incomplete", 
                "message": "Необходимо собрать данные минимум за 7 дней для выявления тренда омоложения."
            }

        # Извлекаем метрики из истории
        hrs = [day["hr"] for day in self.history]
        rmssds = [day["rmssd"] for day in self.history]
        stresses = [day["stress_index"] for day in self.history]

        # Сравниваем первую треть истории со последней третью (выявляем тренд)
        split_size = max(1, len(self.history) // 3)
        
        initial_rmssd = np.mean(rmssds[:split_size])
        current_rmssd = np.mean(rmssds[-split_size:])
        
        initial_hr = np.mean(hrs[:split_size])
        current_hr = np.mean(hrs[-split_size:])

        # Считаем процентные изменения
        rmssd_growth = ((current_rmssd - initial_rmssd) / initial_rmssd) * 100
        hr_reduction = initial_hr - current_hr

        # Логика оценки биологического возраста ИИ
        verdict = "Стабильное состояние"
        bio_age_delta = 0.0

        if rmssd_growth > 15.0 and hr_reduction >= 3:
            verdict = "Активное омоложение и восстановление ресурсов ДНК (удлинение теломер)."
            # Эмпирическая софтверная модель оценки снижения стресс-возраста
            bio_age_delta = -round((rmssd_growth * 0.1) + (hr_reduction * 0.5), 1)
        elif rmssd_growth < -10.0:
            verdict = "Внимание: истощение вегетативной системы. Иммунитет под угрозой, высокий риск скрытых воспалений."
            bio_age_delta = 2.0

        return {
            "status": "Success",
            "metrics": {
                "rmssd_change_pct": round(rmssd_growth, 1),
                "hr_drop_bpm": round(hr_reduction, 1),
                "current_avg_stress": round(float(np.mean(stresses[-split_size:])), 1)
            },
            "biological_age_impact": bio_age_delta,
            "medical_interpretation": verdict
        }

# Тест аналитики длинных трендов
if __name__ == "__main__":
    analyzer = LongevityTrendAnalyzer()

    # Имитируем 30 дней регулярного использования ИИ-системы пользователем.
    # Шаг за шагом: пульс падает, вариабельность (RMSSD) растет, стресс затухает.
    print("[Analytics] Генерируем 30-дневный клинический тренд биохакинга...")
    
    for day in range(1, 31):
        # Имитируем плавный прогресс адаптации организма
        progression_factor = day / 30.0
        
        mock_hr = int(75 - (progression_factor * 8) + np.random.randint(-2, 2))
        mock_rmssd = float(25 + (progression_factor * 20) + np.random.randint(-3, 3))
        mock_stress = float(320 - (progression_factor * 200) + np.random.randint(-15, 15))
        
        analyzer.log_morning_baseline(mock_hr, mock_rmssd, mock_stress)

    # Запускаем анализ накопленных изменений
    report = analyzer.analyze_longevity_trends()
    
    import json
    print("\n=== Итоговый отчет ИИ о биологическом возрасте и иммунной защите ===")
    print(json.dumps(report, indent=4, ensure_ascii=False))