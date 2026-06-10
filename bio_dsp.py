import numpy as np

class BioSignalProcessor:
    def __init__(self, window_size=120):
        """
        window_size: размер буфера памяти в секундах (120 секунд достаточно для MVP)
        """
        self.rr_buffer = []
        self.window_size_ms = window_size * 1000 # Переводим в миллисекунды

    def add_rr_interval(self, rr_ms):
        """Добавляет новый R-R интервал в буфер и удаляет устаревшие"""
        if rr_ms <= 0:
            return
        
        self.rr_buffer.append(rr_ms)
        
        # Удерживаем скользящее окно (чтобы данные не копились бесконечно)
        while sum(self.rr_buffer) > self.window_size_ms:
            self.rr_buffer.pop(0)

    def calculate_rmssd(self):
        """
        RMSSD — главный маркер активности блуждающего нерва (парасимпатики).
        Чем он ВЫШЕ, тем сильнее гасится воспаление.
        """
        if len(self.rr_buffer) < 5:
            return 0.0
        
        # Считаем разности между соседними ударами
        diffs = np.diff(self.rr_buffer)
        # Квадрат разностей -> среднее -> корень
        rmssd = np.sqrt(np.mean(diffs ** 2))
        return round(float(rmssd), 1)

    def calculate_baevsky_stress_index(self):
        """
        Индекс напряжения Баевского (SI).
        Показывает уровень прессинга симпатической системы и боли.
        Норма: 50 - 150. Стресс/Боль: > 300.
        """
        if len(self.rr_buffer) < 20:
            return 100.0 # Возвращаем норму, пока буфер копится
        
        rr_array = np.array(self.rr_buffer)
        
        # 1. Мода (Mo) — наиболее часто встречающийся интервал (с шагом в 50мс)
        # Округляем до ближайших 50мс для построения гистограммы
        rounded_rr = np.round(rr_array / 50) * 50
        values, counts = np.unique(rounded_rr, return_counts=True)
        mo_index = np.argmax(counts)
        mo = values[mo_index] / 1000.0 # в секунды
        
        # 2. Амплитуда моды (AMo) — процент ударов, равных моде
        amo = (counts[mo_index] / len(rr_array)) * 100.0
        
        # 3. Вариационный размах (MxDMn) — разница между макс и мин интервалом
        mx_d_mn = (np.max(rr_array) - np.min(rr_array)) / 1000.0 # в секунды
        
        # Если размах нулевой (пульс-метроном при дичайшем стрессе), защищаем от деления на ноль
        if mx_d_mn == 0:
            mx_d_mn = 0.05
            
        # Формула Баевского
        stress_index = amo / (2 * mo * mx_d_mn)
        
        return round(float(stress_index), 1)

    # Логический набросок для интеграции в bio_dsp.py
    def check_cardio_danger_zones(stress_index, rmssd, current_hr):
        """Проверка критических зон, угрожающих жизни"""
        if stress_index > 800 and rmssd < 5 and current_hr > 100:
            return {
                "status": "CRITICAL_DANGER",
                "alert": "⚠️ ОБНАРУЖЕН ПРЕД-ИНФАРКТНЫЙ ПРОФИЛЬ СЕРДЦА. СРОЧНО ВЫЗОВИТЕ СКОРУЮ ПОМОЩЬ!"
            }
        return {"status": "NORMAL"}

# Тест математического модуля
if __name__ == "__main__":
    dsp = BioSignalProcessor()
    
    # Сценарий 1: Эмуляция здорового, расслабленного сердца (высокая вариабельность)
    print("=== Тест: Расслабленное состояние ===")
    healthy_rr = [1000 + int(np.sin(i) * 50) + np.random.randint(-10, 10) for i in range(100)]
    for rr in healthy_rr:
        dsp.add_rr_interval(rr)
    print(f"Блуждающий нерв (RMSSD): {dsp.calculate_rmssd()} ms (Норма > 40)")
    print(f"Индекс стресса Баевского: {dsp.calculate_baevsky_stress_index()} у.е. (Норма 50-150)")
    
    # Сценарий 2: Эмуляция зажатого состояния / острой боли (пульс-метроном)
    print("\n=== Тест: Острая мышечная боль ===")
    dsp_stress = BioSignalProcessor()
    stressed_rr = [800 + np.random.randint(-3, 3) for i in range(100)] # Почти нет разброса
    for rr in stressed_rr:
        dsp_stress.add_rr_interval(rr)
    print(f"Блуждающий нерв (RMSSD): {dsp_stress.calculate_rmssd()} ms (Критически мало)")
    print(f"Индекс стресса Баевского: {dsp_stress.calculate_baevsky_stress_index()} у.е. (Жесткий стресс/спазм)")