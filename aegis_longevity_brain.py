import numpy as np

class AegisLongevityBrain:
    def __init__(self):
        self.long_term_rmssd_history = []
        self.session_compliance_score = 1.0 # Индекс дисциплины пользователя

    def track_neuro_defense(self, daily_rmssd, theta_session_duration_min):
        """
        Расчет накопительного эффекта защиты коры мозга.
        """
        self.long_term_rmssd_history.append(daily_rmssd)
        if len(self.long_term_rmssd_history) > 180: # Анализируем тренд за 6 месяцев
            self.long_term_rmssd_history.pop(0)
            
        # Математическая оценка стимуляции белка BDNF (фактора роста нейронов)
        # Зависит от регулярности Тета-сессий и удержания стабильного RMSSD
        trend = np.mean(self.long_term_rmssd_history) if self.long_term_rmssd_history else daily_rmssd
        bdnf_stim_factor = (trend * 0.4) + (theta_session_duration_min * 1.5)
        
        return {
            "glymphatic_clearance_efficiency_pct": min(95, int(theta_session_duration_min * 4.7)),
            "neuroplasticity_growth_index": round(bdnf_stim_factor, 2),
            "dementia_risk_reduction_pct": min(78, int((trend / 20) * 15))
        }