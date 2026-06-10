import tkinter as tk
import math
import random
import json
import threading
import time

# Попытка импорта BrainFlow для работы с реальным железом Muse 2
try:
    import brainflow
    from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
    from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations
    BRAINFLOW_AVAILABLE = True
except ImportError:
    BRAINFLOW_AVAILABLE = False


# ==============================================================================
# МОДУЛЬ BRAINFLOW ДЛЯ ПОДКЛЮЧЕНИЯ MUSE 2 (Hardware Level)
# ==============================================================================
class MuseHardwareManager:
    def __init__(self):
        self.is_running = False
        self.board = None
        self.eeg_channels = []
        self.sampling_rate = 256
        self.current_alpha_power = 0.5  # Нормированное значение от 0.0 до 1.0
        self.hardware_status = "Отключено (Режим симуляции)"
        
    def start_stream(self):
        """Инициализация сессии BrainFlow в отдельном потоке"""
        if not BRAINFLOW_AVAILABLE:
            self.hardware_status = "Ошибка: библиотека brainflow не установлена"
            print(f"[Aegis Hardware] {self.hardware_status}")
            return False
            
        try:
            params = BrainFlowInputParams()
            # Для Muse 2 используется BoardIds.MUSE_2_BOARD (id: 22)
            # Подключение идет по Bluetooth BLE
            board_id = BoardIds.MUSE_2_BOARD.value
            
            self.board = BoardShim(board_id, params)
            self.board.prepare_session()
            self.board.start_stream()
            
            self.eeg_channels = BoardShim.get_eeg_channels(board_id)
            self.sampling_rate = BoardShim.get_sampling_rate(board_id)
            self.is_running = True
            self.hardware_status = "Muse 2 успешно подключена [Стрим RAW EEG]"
            
            # Запуск фонового воркера для математической обработки спектра
            self.worker_thread = threading.Thread(target=self._update_data_loop, daemon=True)
            self.worker_thread.start()
            print(f"[Aegis Hardware] {self.hardware_status}")
            return True
            
        except Exception as e:
            self.hardware_status = f"Ошибка подключения Muse 2: {str(e)}"
            print(f"[Aegis Hardware] {self.hardware_status}. Переход в демо-режим.")
            self.is_running = False
            return False

    def _update_data_loop(self):
        """Фоновый расчет мощности Альфа-ритма (8-12 Гц) через фильтры BrainFlow"""
        while self.is_running:
            try:
                time.sleep(0.5) # Обновляем метрики мозга 2 раза в секунду
                
                # Берем последние 512 отсчетов (около 2 секунд данных для FFT)
                data = self.board.get_current_board_data(512)
                if data.shape[1] < 256:
                    continue
                    
                alpha_levels = []
                for channel in self.eeg_channels:
                    channel_data = data[channel]
                    
                    # Очистка сигнала: убираем постоянную составляющую и тренд
                    DataFilter.detrend(channel_data, DetrendOperations.CONSTANT.value)
                    
                    # Считаем спектральную мощность (полоса 8.0 - 12.0 Гц)
                    nfft = DataFilter.get_nearest_power_of_two(self.sampling_rate)
                    psd = DataFilter.get_custom_psd(channel_data, self.sampling_rate, nfft, FilterTypes.BLACKMAN_HARRIS.value)
                    
                    # Извлекаем усредненное значение Альфа-диапазона
                    alpha_band = DataFilter.get_band_power(psd, 8.0, 12.0)
                    alpha_levels.append(alpha_band)
                
                # Вычисляем среднее по всем датчикам и нормируем (усредненный показатель расслабления)
                raw_alpha = sum(alpha_levels) / len(alpha_levels) if alpha_levels else 0
                
                # Масштабируем под интерфейс (0.0 - 1.0) с ограничением лимитов
                self.current_alpha_power = min(max(raw_alpha / 20.0, 0.05), 1.0)
                
            except Exception as e:
                print(f"[Aegis Hardware Loop Error] {e}")
                
    def stop_stream(self):
        """Безопасное закрытие сессии работы с портами"""
        self.is_running = False
        if self.board and self.board.is_prepared():
            self.board.stop_stream()
            self.board.release_session()
            self.hardware_status = "Сессия Muse 2 успешно завершена."


# ==============================================================================
# ИИ-ОРКЕСТРАТОР (Встроенное когнитивное ядро AegisNeuro)
# ==============================================================================
class AICognitiveOrchestrator:
    def __init__(self):
        self.session_context = {}
        self.user_medical_profile = {
            "endocrine_issues": False,    
            "pelvic_congestion": True,    
            "cardio_limitations": False   
        }
        
    def run_intake_assessment(self, user_complaint):
        """Когнитивный анализ текущей жалобы с учетом мед-профиля"""
        complaint_lower = user_complaint.lower()
        strategy = {}

        if "таз" in complaint_lower or "простат" in complaint_lower or "застой" in complaint_lower or "плановое сканирование" in complaint_lower:
            if self.user_medical_profile["pelvic_congestion"]:
                strategy = self._adjust_for_pelvic_health()
                self.session_context = strategy
                return strategy
            
        if "острая" in complaint_lower or "прострел" in complaint_lower or "мигрень" in complaint_lower:
            strategy = {
                "protocol": "theta_anesthesia",
                "target_frequency": 5.5,
                "base_frequency": 140.0,
                "voice_guidance_mode": "глубокий, гипнотический транс"
            }
        else:
            strategy = {
                "protocol": "alpha_relaxation",
                "target_frequency": 10.0,
                "base_frequency": 160.0,
                "voice_guidance_mode": "мягкий, поддерживающий гид"
            }

        if self.user_medical_profile["endocrine_issues"]:
            strategy = {
                "protocol": "endocrine_alpha_safe",
                "target_frequency": 9.5,
                "base_frequency": 150.0,
                "voice_guidance_mode": "эндокринная релаксация (тепло в области шеи)"
            }
            
        self.session_context = strategy
        return strategy

    def _adjust_for_pelvic_health(self):
        return {
            "protocol": "pelvic_resonance_safe",
            "target_frequency": 7.83, 
            "base_frequency": 110.0,  
            "voice_guidance_mode": "тазовое расслабление (снятие зажимов)"
        }

    def generate_live_biofeedback_prompt(self, current_stress, current_rmssd, alpha_power):
        """Формирует инструкции на основе комбинации ЧСС-метрик и Альфа-индекса мозга"""
        protocol = self.session_context.get("protocol", "alpha_relaxation")
        
        # Если реальный альфа-ритм высокий (пользователь расслаблен)
        if alpha_power > 0.65:
            return "Отличная глубина альфа-волн. Мозг вошел в режим нейропластичности и восстановления клеток."
            
        if protocol == "endocrine_alpha_safe":
            return "Опустите плечи. Направьте выдох и внутреннее тепло мягко в область щитовидной железы."
        elif protocol == "pelvic_resonance_safe":
            return "Разомкните мышечный зажим внизу живота. Позвольте кровотоку свободно циркулировать."
                
        if current_stress > 250:
            return "Зафиксируйте внимание на центре сферы. Сделайте выдох длиннее, чем вдох."
        else:
            return "Ритмы сердца и мозга синхронизированы. Наслаждайтесь состоянием покоя."


# ==============================================================================
# ОБЪЕДИНЕННЫЙ ИНТЕРФЕЙС GUI (AegisNeuro OS v1.0)
# ==============================================================================
class AegisNeuroGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AegisNeuro OS v1.0 — Панель управления")
        self.root.geometry("600(x)770")
        self.root.geometry("600x770")
        self.root.configure(bg='#11141a')

        # Инициализация аппаратного менеджера Muse 2 и ИИ-мозга
        self.hardware_manager = MuseHardwareManager()
        self.ai_orchestrator = AICognitiveOrchestrator()

        # Базовые показатели телеметрии
        self.current_stress = 380.0  
        self.current_rmssd = 20.0    
        self.pulse_phase = 0.0
        
        self.setup_ui()
        
        # Пытаемся подключить Muse 2 при старте приложения
        self.hardware_manager.start_stream()
        self.update_hardware_status_ui()

    def setup_ui(self):
        # Главный заголовок
        tk.Label(
            self.root, 
            text="КОНТУР НЕЙРОБИОРЕГУЛЯЦИИ И ОМОЛОЖЕНИЯ", 
            font=("Helvetica", 14, "bold"), bg='#11141a', fg='#00ffcc'
        ).pack(pady=12)

        # ----------------------------------------------------
        # ПАНЕЛЬ СТАТУСА ЖЕЛЕЗА (MUSE 2 ПОДКЛЮЧЕНИЕ)
        # ----------------------------------------------------
        hw_frame = tk.Frame(self.root, bg='#181c26', bd=1, relief="solid")
        hw_frame.pack(pady=5, fill="x", padx=40)
        
        self.hw_status_label = tk.Label(
            hw_frame, text="Поиск ЭЭГ-гарнитуры Muse 2...",
            font=("Helvetica", 10, "bold"), bg='#181c26', fg='#e2e8f0'
        )
        self.hw_status_label.pack(side="left", padx=15, pady=6)
        
        # Кнопка ручного перезапуска поиска устройства, если оно отвалилось
        self.reconnect_btn = tk.Button(
            hw_frame, text="Переподключить", font=("Helvetica", 8, "bold"),
            bg='#1e293b', fg='#00ffcc', activebackground='#0f172a', activeforeground='#00ffcc',
            bd=0, cursor="hand2", padx=10, command=self.manual_hardware_reconnect
        )
        self.reconnect_btn.pack(side="right", padx=15)

        # ----------------------------------------------------
        # СЕЛЕКТОР БИОЛОГИЧЕСКОГО ПРОФИЛЯ
        # ----------------------------------------------------
        gender_frame = tk.LabelFrame(
            self.root, text=" Биологический профиль пользователя ", 
            font=("Helvetica", 10, "italic"), bg='#11141a', fg='#8892b0', bd=1, relief="solid"
        )
        gender_frame.pack(pady=8, fill="x", padx=40)

        self.gender_var = tk.StringVar(value="male")

        male_btn = tk.Radiobutton(
            gender_frame, text="Мужской профиль (Защита простаты / Кардио)", 
            variable=self.gender_var, value="male", command=self.update_gender_profile,
            bg='#11141a', fg='#ffffff', selectcolor='#1a1f29', activebackground='#11141a', font=("Helvetica", 10)
        )
        male_btn.pack(anchor="w", padx=20, pady=4)

        female_btn = tk.Radiobutton(
            gender_frame, text="Женский профиль (Эндокринная / Гинекологическая защита)", 
            variable=self.gender_var, value="female", command=self.update_gender_profile,
            bg='#11141a', fg='#ffffff', selectcolor='#1a1f29', activebackground='#11141a', font=("Helvetica", 10)
        )
        female_btn.pack(anchor="w", padx=20, pady=4)

        # ----------------------------------------------------
        # ФРЕЙМ ТЕЛЕМЕТРИИ ДАТЧИКОВ (СЕРДЦЕ + МОЗГ)
        # ----------------------------------------------------
        stats_frame = tk.Frame(self.root, bg='#1a1f29', bd=1, relief="flat")
        stats_frame.pack(pady=8, fill="x", padx=40)

        self.stress_label = tk.Label(stats_frame, text="", font=("Helvetica", 11), bg='#1a1f29', fg='#ff5555')
        self.stress_label.pack(pady=3)

        self.rmssd_label = tk.Label(stats_frame, text="", font=("Helvetica", 11), bg='#1a1f29', fg='#55ff55')
        self.rmssd_label.pack(pady=3)
        
        self.eeg_alpha_label = tk.Label(
            stats_frame, text="Мощность Альфа-ритма (Muse 2): 0.0%", 
            font=("Helvetica", 11, "bold"), bg='#1a1f29', fg='#38bdf8'
        )
        self.eeg_alpha_label.pack(pady=3)

        # ----------------------------------------------------
        # ИИ-ПАНЕЛЬ СОВЕТОВ И ТЕКУЩИХ РЕЖИМОВ
        # ----------------------------------------------------
        self.ai_status_frame = tk.Frame(self.root, bg='#0d1117', bd=1, relief="solid")
        self.ai_status_frame.pack(pady=5, fill="x", padx=40)
        
        self.ai_protocol_label = tk.Label(
            self.ai_status_frame, text="Протокол ИИ: инициализация...",
            font=("Helvetica", 10, "bold"), bg='#0d1117', fg='#38bdf8'
        )
        self.ai_protocol_label.pack(pady=2, anchor="w", padx=15)
        
        self.ai_voice_label = tk.Label(
            self.ai_status_frame, text="ИИ-Голос: расчет биофидбэка...",
            font=("Helvetica", 9, "italic"), bg='#0d1117', fg='#94a3b8', wraplength=480, justify="left"
        )
        self.ai_voice_label.pack(pady=4, anchor="w", padx=15)

        # Холст для отрисовки пульсирующей сферы биофидбэка
        self.canvas = tk.Canvas(self.root, width=340, height=340, bg='#11141a', highlightthickness=0)
        self.canvas.pack(pady=5)

        # Текстовая подсказка по дыханию
        self.breath_instruction = tk.Label(
            self.root, text="", font=("Helvetica", 12, "italic"), bg='#11141a', fg='#8892b0'
        )
        self.breath_instruction.pack(pady=5)

        # Синхронизация логики
        self.update_gender_profile()
        self.update_gui_loop()

    def update_hardware_status_ui(self):
        """Обновление цветовой индикации подключения железа в GUI"""
        status_text = self.hardware_manager.hardware_status
        self.hw_status_label.config(text=status_text)
        if "успешно подключена" in status_text:
            self.hw_status_label.config(fg='#55ff55')
        elif "Ошибка" in status_text:
            self.hw_status_label.config(fg='#ff5555')
        else:
            self.hw_status_label.config(fg='#cca300') # Демо-режим

    def manual_hardware_reconnect(self):
        """Ручной перезапуск потока инициализации BLE-портов"""
        self.hw_status_label.config(text="Повторная попытка коннекта BLE...", fg='#e2e8f0')
        self.root.update_idletasks()
        self.hardware_manager.stop_stream()
        self.hardware_manager.start_stream()
        self.update_hardware_status_ui()

    def update_gender_profile(self):
        selected_gender = self.gender_var.get()
        if selected_gender == "male":
            self.ai_orchestrator.user_medical_profile["pelvic_congestion"] = True
            self.ai_orchestrator.user_medical_profile["endocrine_issues"] = False
            print("[GUI -> ИИ] Активирован МУЖСКОЙ контур (AegisPelvic-Male).")
        else:
            self.ai_orchestrator.user_medical_profile["pelvic_congestion"] = False
            self.ai_orchestrator.user_medical_profile["endocrine_issues"] = True
            print("[GUI -> ИИ] Активирован ЖЕНСКИЙ контур (AegisEndocrine-Female).")
            
        strategy = self.ai_orchestrator.run_intake_assessment("Плановое сканирование")
        self.ai_protocol_label.config(text=f"Режим ИИ: {strategy['protocol'].upper()}")

    def get_sphere_color(self, stress):
        if stress > 250: return "#ff3333"  # Стресс
        elif 150 < stress <= 250: return "#ffaa00"  # Напряжение
        else: return "#00ff66"  # Регенерация

    def update_gui_loop(self):
        """Единый замкнутый цикл анимации, симуляции деградации стресса и вызовов биофидбэка ИИ"""
        self.canvas.delete("all")

        # Чтение Альфа-мощности из потока BrainFlow (или симуляция, если Muse отключен)
        if self.hardware_manager.is_running:
            alpha_power = self.hardware_manager.current_alpha_power
        else:
            # Математическая имитация волновой активности мозга для демо-режима
            alpha_power = 0.4 + (math.sin(self.pulse_phase * 1.5) * 0.2) + random.uniform(-0.03, 0.03)
            alpha_power = min(max(alpha_power, 0.0), 1.0)

        # Плавная деградация (уменьшение) стресса на основе альфа-биофидбэка
        # Чем выше альфа-ритм (расслабление), тем быстрее падает индекс стресса!
        if self.current_stress > 70:
            self.current_stress -= (0.2 + (alpha_power * 0.4))
            self.current_rmssd += (0.02 + (alpha_power * 0.04))
        
        # Обновление текстовой телеметрии
        self.stress_label.config(text=f"Индекс Стресса (Aegis Metric): {int(self.current_stress)} у.е.")
        self.rmssd_label.config(text=f"Тонус вегетативной системы (RMSSD): {int(self.current_rmssd)} ms")
        self.eeg_alpha_label.config(text=f"Мощность Альфа-ритма (ЭЭГ): {int(alpha_power * 100)}%")

        # Дыхательный резонанс
        self.pulse_phase += 0.04
        # Модифицируем радиус сферы: если альфа-ритм высокий, сфера "дышит" стабильнее и шире
        radius = 100 + int(math.sin(self.pulse_phase) * (40 + (alpha_power * 15)))

        if math.cos(self.pulse_phase) > 0:
            self.breath_instruction.config(text="ПЛАВНЫЙ ВДОХ...", fg='#00ffcc')
        else:
            self.breath_instruction.config(text="ГЛУБОКИЙ ВЫДОХ [РАССЛАБЛЕНИЕ]...", fg='#8892b0')

        # Запрос динамической речевой подсказки у ИИ
        ai_phrase = self.ai_orchestrator.generate_live_biofeedback_prompt(
            current_stress=self.current_stress,
            current_rmssd=self.current_rmssd,
            alpha_power=alpha_power
        )
        self.ai_voice_label.config(text=f'Голос ИИ в наушниках: "{ai_phrase}"')

        # Координаты сферы (холст 340x340 -> центр 170, 170)
        center_x, center_y = 170, 170
        x0, y0 = center_x - radius, center_y - radius
        x1, y1 = center_x + radius, center_y + radius

        color = self.get_sphere_color(self.current_stress)

        # Отрисовка неона и тела сферы
        self.canvas.create_oval(x0-8, y0-8, x1+8, y1+8, fill="", outline=color, width=1.5)
        self.canvas.create_oval(x0, y0, x1, y1, fill=color, outline="")

        # Планирование следующего кадра GUI
        self.root.after(30, self.update_gui_loop)

    def on_closing(self):
        """Корректное завершение при закрытии крестиком"""
        self.hardware_manager.stop_stream()
        self.root.destroy()

if __name__ == "__main__":
    gui = AegisNeuroGUI()
    gui.root.protocol("WM_DELETE_WINDOW", gui.on_closing)
    gui.run()