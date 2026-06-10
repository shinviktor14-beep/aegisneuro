import time
import random

class BioFeedbackController:
    def __init__(self):
        # Целевые показатели здорового расслабления (индекс Баевского)
        # Норма в покое: 50 - 150 у.е.
        # Стресс/Боль: > 300 - 500 у.е.
        self.target_stress_low = 50
        self.target_stress_high = 120
        
        # Стартовое состояние «виртуального пользователя» (высокий стресс/боль)
        self.current_user_stress = 450.0 
        
        # Начальная частота стимуляции (начинаем с легкого Альфа-расслабления)
        self.current_audio_frequency = 12.0 

    def get_mock_polar_data(self):
        """
        Имитация получения данных с Polar H10.
        В реальности здесь будет подписка на BLE-поток R-R интервалов.
        """
        # Имитируем, что под воздействием правильного звука стресс постепенно падает,
        # но имеет случайные флуктуации (как у живого сердца)
        decay = 0.0
        
        # Если мы попали в глубокий Тета-диапазон (4-7 Гц), тело расслабляется быстрее
        if 4.0 <= self.current_audio_frequency <= 7.0:
            decay = random.uniform(8.0, 15.0) # Быстрое снятие боли
        elif 8.0 <= self.current_audio_frequency <= 12.0:
            decay = random.uniform(3.0, 7.0)  # Мягкий релакс
        else:
            decay = random.uniform(-2.0, 2.0) # Частота не подобрана, стресс на месте
            
        self.current_user_stress -= decay
        
        # Ограничиваем рамками физиологии
        if self.current_user_stress < 40: 
            self.current_user_stress = 40
            
        return round(self.current_user_stress, 1)

    def update_frequency(self, current_stress):
        """
        Главный алгоритм ИИ. Принимает стресс из Polar, возвращает нужную частоту для наушников.
        """
        # Логика закрытого контура (Closed-Loop):
        if current_stress > 300:
            # Жесткий стресс или острая мышечная боль. 
            # Агрессивно уводим мозг в глубокий Тета-ритм для «анестезии»
            self.current_audio_frequency = 5.5
            action = "Острая боль/Стресс. Включаем Тета-анестезию."
            
        elif 150 < current_stress <= 300:
            # Умеренное напряжение. Мозг сопротивляется, но начинает расслабляться.
            # Держим на границе Альфа/Тета для мягкого торможения симпатики
            self.current_audio_frequency = 7.5
            action = "Умеренное напряжение. Балансируем на стыке Альфа/Тета."
            
        elif self.target_stress_high >= current_stress >= self.target_stress_low:
            # Мы вошли в зеленую зону! Блуждающий нерв активирован, воспаление и спазмы гасятся.
            # Закрепляем успех на классической чистой частоте Альфа-резонанса
            self.current_audio_frequency = 10.0
            action = "Цель достигнута! Тело в режиме регенерации. Удерживаем Альфа-ритм."
            
        else:
            # Пользователь слишком расслабился (засыпает).
            # Чуть приподнимаем частоту, чтобы не провалиться в глубокий сон (если это не вечерний протокол)
            self.current_audio_frequency = 11.5
            action = "Глубокий релакс. Мягко поддерживаем тонус."

        return self.current_audio_frequency, action

# Демонстрация работы контура
if __name__ == "__main__":
    controller = BioFeedbackController()
    print("=== Запуск ИИ-контроллера биорегуляции (Эмуляция) ===")
    print(f"Стартовый стресс пользователя: {controller.current_user_stress} у.е. (Острая боль)\n")
    
    for second in range(1, 16):
        stress = controller.get_mock_polar_data()
        freq, decision = controller.update_frequency(stress)
        
        print(f"[Секунда {second:02d}] Пульс/ВСР (Стресс-индекс): {stress:5s} у.е. | ИИ подает в наушники: {freq:4.1f} Гц")
        print(f"            └─ Решение ИИ: {decision}")
        print("-" * 80)
        time.sleep(1)