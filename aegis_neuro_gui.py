import tkinter as tk
import math
import random

# Импортируем ядра из пакета aegis
from aegis.core import MuseHardwareManager, AICognitiveOrchestrator


# ==============================================================================
# ОБЪЕДИНЕННЫЙ ИНТЕРФЕЙС GUI (AegisNeuro OS v1.0)
# ==============================================================================
class AegisNeuroGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AegisNeuro OS v1.0 — Панель управления")
        self.root.geometry("600x770")
        self.root.configure(bg='#11141a')

        self.hardware_manager = MuseHardwareManager()
        self.ai_orchestrator = AICognitiveOrchestrator()

        self.current_stress = 380.0
        self.current_rmssd = 20.0
        self.pulse_phase = 0.0

        self.setup_ui()
        self.hardware_manager.start_stream()
        self.update_hardware_status_ui()

    def setup_ui(self):
        tk.Label(
            self.root,
            text="КОНТУР НЕЙРОБИОРЕГУЛЯЦИИ И ОМОЛОЖЕНИЯ",
            font=("Helvetica", 14, "bold"), bg='#11141a', fg='#00ffcc'
        ).pack(pady=12)

        # ПАНЕЛЬ СТАТУСА ЖЕЛЕЗА (MUSE 2)
        hw_frame = tk.Frame(self.root, bg='#181c26', bd=1, relief="solid")
        hw_frame.pack(pady=5, fill="x", padx=40)

        self.hw_status_label = tk.Label(
            hw_frame, text="Поиск ЭЭГ-гарнитуры Muse 2...",
            font=("Helvetica", 10, "bold"), bg='#181c26', fg='#e2e8f0'
        )
        self.hw_status_label.pack(side="left", padx=15, pady=6)

        self.reconnect_btn = tk.Button(
            hw_frame, text="Переподключить", font=("Helvetica", 8, "bold"),
            bg='#1e293b', fg='#00ffcc', activebackground='#0f172a', activeforeground='#00ffcc',
            bd=0, cursor="hand2", padx=10, command=self.manual_hardware_reconnect
        )
        self.reconnect_btn.pack(side="right", padx=15)

        # СЕЛЕКТОР БИОЛОГИЧЕСКОГО ПРОФИЛЯ
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

        # ТЕЛЕМЕТРИЯ ДАТЧИКОВ
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

        # ИИ-ПАНЕЛЬ
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

        self.canvas = tk.Canvas(self.root, width=340, height=340, bg='#11141a', highlightthickness=0)
        self.canvas.pack(pady=5)

        self.breath_instruction = tk.Label(
            self.root, text="", font=("Helvetica", 12, "italic"), bg='#11141a', fg='#8892b0'
        )
        self.breath_instruction.pack(pady=5)

        self.update_gender_profile()
        self.update_gui_loop()

    def update_hardware_status_ui(self):
        status_text = self.hardware_manager.hardware_status
        self.hw_status_label.config(text=status_text)
        if "подключена" in status_text.lower():
            self.hw_status_label.config(fg='#55ff55')
        elif "Ошибка" in status_text or "ошибка" in status_text:
            self.hw_status_label.config(fg='#ff5555')
        else:
            self.hw_status_label.config(fg='#cca300')

    def manual_hardware_reconnect(self):
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
        else:
            self.ai_orchestrator.user_medical_profile["pelvic_congestion"] = False
            self.ai_orchestrator.user_medical_profile["endocrine_issues"] = True

        strategy = self.ai_orchestrator.run_intake_assessment("Плановое сканирование")
        self.ai_protocol_label.config(text=f"Режим ИИ: {strategy['protocol'].upper()}")

    def get_sphere_color(self, stress):
        if stress > 250: return "#ff3333"
        elif 150 < stress <= 250: return "#ffaa00"
        else: return "#00ff66"

    def update_gui_loop(self):
        self.canvas.delete("all")

        if self.hardware_manager.is_running:
            alpha_power = self.hardware_manager.current_alpha_power
        else:
            alpha_power = 0.4 + (math.sin(self.pulse_phase * 1.5) * 0.2) + random.uniform(-0.03, 0.03)
            alpha_power = min(max(alpha_power, 0.0), 1.0)

        if self.current_stress > 70:
            self.current_stress -= (0.2 + (alpha_power * 0.4))
            self.current_rmssd += (0.02 + (alpha_power * 0.04))

        self.stress_label.config(text=f"Индекс Стресса (Aegis Metric): {int(self.current_stress)} у.е.")
        self.rmssd_label.config(text=f"Тонус вегетативной системы (RMSSD): {int(self.current_rmssd)} ms")
        self.eeg_alpha_label.config(text=f"Мощность Альфа-ритма (ЭЭГ): {int(alpha_power * 100)}%")

        self.pulse_phase += 0.04
        radius = 100 + int(math.sin(self.pulse_phase) * (40 + (alpha_power * 15)))

        if math.cos(self.pulse_phase) > 0:
            self.breath_instruction.config(text="ПЛАВНЫЙ ВДОХ...", fg='#00ffcc')
        else:
            self.breath_instruction.config(text="ГЛУБОКИЙ ВЫДОХ [РАССЛАБЛЕНИЕ]...", fg='#8892b0')

        # ИИ-биофидбэк — новый API: (stress, rmssd, elapsed_time, alpha_power=)
        ai_phrase = self.ai_orchestrator.generate_live_biofeedback_prompt(
            current_stress=self.current_stress,
            current_rmssd=self.current_rmssd,
            elapsed_time=0,
            alpha_power=alpha_power
        )
        self.ai_voice_label.config(text=f'Голос ИИ в наушниках: "{ai_phrase}"')

        center_x, center_y = 170, 170
        x0, y0 = center_x - radius, center_y - radius
        x1, y1 = center_x + radius, center_y + radius

        color = self.get_sphere_color(self.current_stress)

        self.canvas.create_oval(x0-8, y0-8, x1+8, y1+8, fill="", outline=color, width=1.5)
        self.canvas.create_oval(x0, y0, x1, y1, fill=color, outline="")

        self.root.after(30, self.update_gui_loop)

    def on_closing(self):
        self.hardware_manager.stop_stream()
        self.root.destroy()


if __name__ == "__main__":
    gui = AegisNeuroGUI()
    gui.root.protocol("WM_DELETE_WINDOW", gui.on_closing)
    gui.root.mainloop()