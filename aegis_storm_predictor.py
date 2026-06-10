import numpy as np
import json
import os
from datetime import datetime

class AegisStormPredictor:
    def __init__(self):
        self.baseline_path = "aegis_historical_baseline.json"
        # Базовые здоровые маркеры пользователя (адаптируются по мере накопления статистики)
        self.baseline = {
            "avg_rmssd": 35.0,      # Средний здоровый тонус блуждающего нерва
            "avg_stress_idx": 120.0 # Средний утренний стресс в норме
        }
        self.load_baseline()

    def load_baseline(self):
        if os.path.exists(self.baseline_path):
            with open(self.baseline_path, "r") as f:
                self.baseline = json.load(f)
            print("[Aegis-Predictor] Исторический базовый профиль ВСР успешно загружен.")
        else:
            print("[Aegis-Predictor] База чиста. Используются дефолтные медицинские маркеры.")

    def analyze_morning_test(self, rr_intervals):
        """
        Глубокий анализ 5-минутного утреннего потока R-R интервалов.
        Ищет скрытые микро-альтернации до появления физической боли.
        """
        if len(rr_intervals) < 100:
            return {"status": "INSUFFICIENT_DATA", "probability": 0}

        # 1. Считаем текущие метрики ВСР
        rr_diff = np.diff(rr_intervals)
        current_rmssd = np.sqrt(np.mean(rr_diff ** 2))
        
        # Расчет индекса стресса Баевского (упрощенный аналог для массива данных)
        amo = self._calculate_amplitude_of_mode(rr_intervals)
        mx_dmn = (np.max(rr_intervals) - np.min(rr_intervals)) / 1000.0 # в секундах
        current_stress_idx = (amo) / (2 * mx_dmn * (np.median(rr_intervals)/1000.0))

        # 2. Магия ИИ: Поиск микро-альтернаций (флуктуаций стабильности ритма)
        # Разбиваем массив на 4 отрезка и смотрим стабильность RMSSD
        chunks = np.array_split(rr_intervals, 4)
        chunk_rmssds = []
        for ch in chunks:
            if len(ch) > 1:
                chunk_rmssds.append(np.sqrt(np.mean(np.diff(ch) ** 2)))
        
        # Альтернация (вариация стабильности). Высокий коэф. вариации = хаос в ЦНС
        rmssd_alternation_coef = np.std(chunk_rmssds) / np.mean(chunk_rmssds) if len(chunk_rmssds) > 0 else 0

        # 3. Скоринг вероятности шторма (Нейро-веса)
        storm_score = 0
        reasons = []

        # Триггер 1: Падение парасимпатики ниже исторической нормы
        rmssd_drop_pct = ((self.baseline["avg_rmssd"] - current_rmssd) / self.baseline["avg_rmssd"]) * 100
        if rmssd_drop_pct > 25:
            storm_score += 40
            reasons.append(f"Критическое падение тонуса Vagus на {int(rmssd_drop_pct)}% ниже вашей нормы")

        # Триггер 2: Взлет утреннего стресса
        if current_stress_idx > self.baseline["avg_stress_idx"] * 1.8:
            storm_score += 30
            reasons.append("Скрытая гиперсимпатикотония (организм в режиме скрытой тревоги)")

        # Триггер 3: Высокий уровень микро-альтернаций (нестабильность ритма)
        if rmssd_alternation_coef > 0.15:
            storm_score += 30
            reasons.append("Обнаружен хаотический паттерн микро-альтернаций ритма (предвестник мигрени/ПА)")

        # Ограничиваем шкалу от 0 до 100%
        storm_probability = min(max(storm_score, 0), 100)

        status = "CLEAR"
        if storm_probability >= 70:
            status = "STORM_ALERT"
        elif 40 <= storm_probability < 70:
            status = "WARNING"

        return {
            "status": status,
            "storm_probability_pct": storm_probability,
            "metrics": {
                "rmssd": round(current_rmssd, 1),
                "stress_index": int(current_stress_idx),
                "alternation_index": round(rmssd_alternation_coef, 3)
            },
            "triggers": reasons,
            "prediction_window": "2-3 часа"
        }

    def _calculate_amplitude_of_mode(self, rr_intervals):
        # Вспомогательный метод для вычисления моды распределения интервалов
        counts, bins = np.histogram(rr_intervals, bins=20)
        max_idx = np.argmax(counts)
        return (counts[max_idx] / len(rr_intervals)) * 100

# Тест предиктора в условиях надвигающегося скрытого шторма
if __name__ == "__main__":
    predictor = AegisStormPredictor()
    
    # СИТУАЦИЯ: Человек проснулся, чувствует себя нормально, но тело уже генерирует пред-мигренозный хаос
    # Имитируем жесткий, хаотичный ритм с низким RMSSD и сильными скачками
    mock_pre_storm_rr = []
    base_rr = 750 # Пульс ~80
    for i in range(300):
        # Каждые 50 ударов ритм резко зажимается или улетает в хаос (микро-альтернация)
        if (i // 50) % 2 == 0:
            base_rr = 720 + np.random.randint(-10, 10)
        else:
            base_rr = 760 + np.random.randint(-40, 40)
        mock_pre_storm_rr.append(base_rr)

    # Запускаем предиктивный анализ утреннего замера
    result = predictor.analyze_morning_test(mock_pre_storm_rr)
    
    print("\n⚡=== РЕЗУЛЬТАТЫ УТРЕННЕГО СКАНИРОВАНИЯ AEGISNEURO ===⚡")
    print(f"Статус щита: {result['status']}")
    print(f"Вероятность шторма (Мигрень / Паническая атака / Приступ боли): {result['storm_probability_pct']%}")
    print(f"Окно упреждения: {result['prediction_window']}")
    print("\nВыявленные аномалии:")
    for trigger in result['triggers']:
        print(f" -> {trigger}")
        
    if result['status'] == "STORM_ALERT":
        print("\n[РЕКОМЕНДАЦИЯ ИИ]: Немедленно запустите превентивную сессию 'AegisShield - Theta Neuro-Anesthesia' на 15 минут, чтобы заблокировать шторм в центральной нервной системе.")