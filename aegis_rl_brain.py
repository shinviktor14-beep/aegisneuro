import numpy as np
import random
import json
import os

class AegisRLBrain:
    def __init__(self, actions_list=None, alpha=0.2, gamma=0.9, epsilon=0.3):
        # Возможные терапевтические частоты (наши действия)
        # От глубокого Тета (4 Гц) до Альфа (12 Гц) с шагом в 0.5 Гц
        self.actions = actions_list if actions_list else list(np.arange(4.0, 12.5, 0.5))
        
        self.alpha = alpha   # Скорость обучения (Learning Rate)
        self.gamma = gamma   # Фактор дисконтирования (важность будущих наград)
        self.epsilon = epsilon # Шанс исследования (разведки новых частот)
        
        # Состояния среды (Индекс Стресса Баевского, разбитый на зоны):
        # 0: Идеально (<150), 1: Норма (150-300), 2: Напряжение (300-500), 3: Критический стресс (>500)
        self.num_states = 4
        
        # Таблица памяти ИИ (Q-table): Строки - состояния, Столбцы - действия (частоты)
        self.q_table = np.zeros((self.num_states, len(self.actions)))
        self.profile_path = "aegis_user_brain_profile.json"
        self.load_profile()

    def get_state_index(self, stress_index):
        """Перевод непрерывного индекса стресса в дискретное состояние ИИ"""
        if stress_index < 150: return 0
        elif stress_index <= 300: return 1
        elif stress_index <= 500: return 2
        else: return 3

    def choose_frequency(self, current_stress):
        """Выбор частоты: ИИ либо рискует и ищет новое, либо бьет в проверенную точку"""
        state_idx = self.get_state_index(current_stress)
        
        # Эпсилон-жадный алгоритм (Exploration vs Exploitation)
        if random.uniform(0, 1) < self.epsilon:
            # Разведка: выбираем случайную частоту, чтобы протестировать реакцию тела
            action_idx = random.randint(0, len(self.actions) - 1)
            strategy = "Исследование нового био-резонанса"
        else:
            # Эксплуатация: берем частоту, которая давала лучшую награду для этого состояния
            action_idx = np.argmax(self.q_table[state_idx])
            strategy = "Применение оптимального личного паттерна"
            
        return self.actions[action_idx], action_idx, strategy

    def learn(self, old_stress, action_idx, new_stress, rmssd_growth):
        """Коррекция памяти ИИ на основе реального отклика вегетативной системы"""
        old_state = self.get_state_index(old_stress)
        new_state = self.get_state_index(new_stress)
        
        # Считаем награду (Reward): 
        # Чем сильнее упал стресс и чем выше вырос RMSSD — тем выше награда для ИИ
        stress_delta = old_stress - new_stress
        reward = stress_delta + (rmssd_growth * 2)
        
        # Если стресс вырос — ИИ получает штраф (отрицательная награда)
        if stress_delta < 0:
            reward -= 50 

        # Формула Беллмана (Обновление Q-значения)
        old_q = self.q_table[old_state, action_idx]
        max_future_q = np.max(self.q_table[new_state])
        
        # Пересчитываем ценность выбранной частоты
        self.q_table[old_state, action_idx] = old_q + self.alpha * (reward + self.gamma * max_future_q - old_q)

    def save_profile(self):
        """Сохранение уникального цифрового профиля нервной системы на диск"""
        data = {"q_table": self.q_table.tolist(), "actions": self.actions}
        with open(self.profile_path, "w") as f:
            json.dump(data, f)
        print("[Aegis-RL] Цифровой профиль вегетатики успешно синхронизирован с базой.")

    def load_profile(self):
        """Загрузка памяти ИИ при старте сессии"""
        if os.path.exists(self.profile_path):
            with open(self.profile_path, "r") as f:
                data = json.load(f)
                self.q_table = np.array(data["q_table"])
                print("[Aegis-RL] Загружен предобученный профиль нервной системы.")
        else:
            print("[Aegis-RL] Чистый профиль. ИИ начинает обучение с нуля.")

# Демонстрационный тест самообучения ИИ
if __name__ == "__main__":
    brain = AegisRLBrain()
    
    # Симулируем 15 шагов одной сессии, где ИИ пытается успокоить тело
    simulated_stress = 450.0 # Стартуем с сильного стресса
    
    print("\n--- СТАРТ СЕССИИ САМООБУЧЕНИЯ True AI ---")
    for step in range(1, 16):
        old_stress = simulated_stress
        
        # ИИ выбирает частоту на основе текущего стресса
        freq, act_idx, strat = brain.choose_frequency(old_stress)
        
        # Симулируем отклик тела: предположим, что наше тело идеально
        # реагирует ТОЛЬКО на частоты в районе 5.5 - 6.5 Гц (глубокий Тета-резонанс)
        if 5.0 <= freq <= 6.5:
            simulated_stress -= random.uniform(25, 40) # Стресс падает мощно
            mock_rmssd_growth = 15.0
        else:
            simulated_stress -= random.uniform(-10, 10) # Стресс топчется на месте или растет
            mock_rmssd_growth = -2.0
            
        # Ограничиваем нижнюю планку стресса здоровым минимумом
        if simulated_stress < 60: simulated_stress = 60.0
        
        # ИИ анализирует изменения и перестраивает свою Q-таблицу памяти
        brain.learn(old_stress, act_idx, simulated_stress, mock_rmssd_growth)
        
        print(f"Шаг {step} | Стресс: {int(old_stress)} -> {int(simulated_stress)} | Выбрана частота: {freq} Гц | Стратегия: {strat}")
        
    # Сохраняем опыт
    brain.save_profile()