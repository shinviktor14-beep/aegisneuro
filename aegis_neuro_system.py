import tkinter as tk
import math
import random
import threading
import time

import numpy as np

# Импортируем ядра из пакета aegis
from aegis.core import AegisRLBrain, MuseHardwareManager


# ==============================================================================
# ИНТЕРФЕЙС УПРАВЛЕНИЯ С ИНТЕГРИРОВАННЫМ ЦИКЛОМ ОБУЧЕНИЯ
# ==============================================================================
class AegisNeuroGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AegisNeuro OS v1.0 — RL Brain Integration")
        self.root.geometry("600x750")
        self.root.configure(bg='#11141a')

        self.ai_brain = AegisRLBrain()
        self.hardware_manager = MuseHardwareManager()

        self.current_stress = 380.0
        self.current_rmssd = 25.0
        self.pulse_phase = 0.0

        self.rl_old_stress = self.current_stress
        self.rl_old_rmssd = self.current_rmssd
        self.rl_current_action_idx = 0
        self.current_target_freq = 8.0
        self.current_strategy_text = "Инициализация вегетативного ядра..."

        self.setup_ui()
        self.hardware_manager.start_stream()
        self.update_hardware_status_ui()

        self.rl_step_interval_ms = 10000
        self.root.after(self.rl_step_interval_ms, self.execute_rl_learning_step)

    def setup_ui(self):
        tk.Label(self.root, text="КОНТУР НЕЙРОПОДКРЕПЛЕНИЯ AEGIS-RL", font=("Helvetica", 13, "bold"), bg='#11141a', fg='#00ffcc').pack(pady=10)

        hw_frame = tk.Frame(self.root, bg='#181c26', bd=1, relief="solid")
        hw_frame.pack(pady=2, fill="x", padx=40)
        self.hw_status_label = tk.Label(hw_frame, text="", font=("Helvetica", 9, "bold"), bg='#181c26', fg='#e2e8f0')
        self.hw_status_label.pack(side="left", padx=15, pady=5)

        ai_frame = tk.LabelFrame(self.root, text=" Мониторинг решений AegisRLBrain ", font=("Helvetica", 9, "italic"), bg='#11141a', fg='#8892b0', bd=1, relief="solid")
        ai_frame.pack(pady=10, fill="x", padx=40)

        self.ai_strategy_label = tk.Label(ai_frame, text="Стратегия: Вычисление...", font=("Helvetica", 10, "bold"), bg='#11141a', fg='#38bdf8', anchor="w")
        self.ai_strategy_label.pack(fill="x", padx=15, pady=2)

        self.ai_freq_label = tk.Label(ai_frame, text="Генерируемая частота: -- Гц", font=("Helvetica", 10), bg='#11141a', fg='#ffffff', anchor="w")
        self.ai_freq_label.pack(fill="x", padx=15, pady=2)

        self.ai_log_label = tk.Label(ai_frame, text="Лог Bellman Equation: ожидание шага...", font=("Helvetica", 8), bg='#11141a', fg='#a1a1aa', anchor="w")
        self.ai_log_label.pack(fill="x", padx=15, pady=4)

        stats_frame = tk.Frame(self.root, bg='#1a1f29', bd=1, relief="flat")
        stats_frame.pack(pady=5, fill="x", padx=40)
        self.stress_label = tk.Label(stats_frame, text="", font=("Helvetica", 11), bg='#1a1f29', fg='#ff5555')
        self.stress_label.pack(pady=2)
        self.rmssd_label = tk.Label(stats_frame, text="", font=("Helvetica", 11), bg='#1a1f29', fg='#55ff55')
        self.rmssd_label.pack(pady=2)

        self.canvas = tk.Canvas(self.root, width=300, height=300, bg='#11141a', highlightthickness=0)
        self.canvas.pack(pady=5)

        self.update_gui_loop()

    def update_hardware_status_ui(self):
        status_text = self.hardware_manager.hardware_status
        self.hw_status_label.config(text=status_text)
        if "ПОТОК" in status_text.upper():
            self.hw_status_label.config(fg='#55ff55')
        else:
            self.hw_status_label.config(fg='#cca300')

    def execute_rl_learning_step(self):
        """Реальный шаг обучения ИИ"""
        new_stress = self.current_stress
        new_rmssd = self.current_rmssd
        rmssd_growth = new_rmssd - self.rl_old_rmssd

        self.ai_brain.learn(
            old_stress=self.rl_old_stress,
            action_idx=self.rl_current_action_idx,
            new_stress=new_stress,
            rmssd_growth=rmssd_growth
        )

        state_idx = self.ai_brain.get_state_index(new_stress)
        self.ai_log_label.config(
            text=f"Q-Update: State {state_idx} | Reward: {int((self.rl_old_stress - new_stress) + (rmssd_growth*2))} | Profile Saved"
        )

        self.ai_brain.save_profile()

        self.current_target_freq, self.rl_current_action_idx, self.current_strategy_text = self.ai_brain.choose_frequency(new_stress)

        self.ai_strategy_label.config(text=f"Стратегия: {self.current_strategy_text}")
        self.ai_freq_label.config(text=f"Терапевтический резонанс: {self.current_target_freq} Гц")

        self.rl_old_stress = new_stress
        self.rl_old_rmssd = new_rmssd

        self.root.after(self.rl_step_interval_ms, self.execute_rl_learning_step)

    def update_gui_loop(self):
        self.canvas.delete("all")

        if self.hardware_manager.is_running:
            alpha_power = self.hardware_manager.current_alpha_power
            if 5.5 <= self.current_target_freq <= 7.0:
                self.current_stress -= (0.4 + alpha_power * 0.3)
                self.current_rmssd += 0.08
            else:
                self.current_stress += random.uniform(-0.2, 0.3)
        else:
            alpha_power = 0.3 + (math.sin(self.pulse_phase) * 0.1)
            self.current_stress -= 0.05
            self.current_rmssd += 0.01

        self.current_stress = min(max(self.current_stress, 55.0), 650.0)
        self.current_rmssd = min(max(self.current_rmssd, 15.0), 120.0)

        self.stress_label.config(text=f"Индекс Стресса Баевского: {int(self.current_stress)} у.е.")
        self.rmssd_label.config(text=f"Вегетативный тонус (RMSSD): {int(self.current_rmssd)} ms")

        self.pulse_phase += 0.05
        base_radius = 80 + (self.current_target_freq * 3)
        radius = base_radius + int(math.sin(self.pulse_phase) * (30 + alpha_power * 15))

        if self.current_stress > 300: color = "#ff3333"
        elif 150 < self.current_stress <= 300: color = "#ffaa00"
        else: color = "#00ff66"

        cx, cy = 150, 150
        self.canvas.create_oval(cx - radius - 6, cy - radius - 6, cx + radius + 6, cy + radius + 6, fill="", outline=color, width=1)
        self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill=color, outline="")

        self.root.after(30, self.update_gui_loop)

    def on_closing(self):
        self.hardware_manager.stop_stream()
        self.ai_brain.save_profile()
        self.root.destroy()


if __name__ == "__main__":
    gui = AegisNeuroGUI()
    gui.root.protocol("WM_DELETE_WINDOW", gui.on_closing)
    gui.root.mainloop()