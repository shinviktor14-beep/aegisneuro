"""Q-learning мозг: 4 состояния стресса × 18 частот (4–12 Гц шаг 0.5).

Источник: ``aegis_rl_brain.py`` (канон). Q-таблица хранится в
``data/brain_profile.json`` — не в CWD.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np

from aegis import config


class AegisRLBrain:
    def __init__(
        self,
        actions: list[float] | None = None,
        alpha: float = config.RL_ALPHA,
        gamma: float = config.RL_GAMMA,
        epsilon: float = config.RL_EPSILON,
        profile_path: Path = config.BRAIN_PROFILE_PATH,
    ) -> None:
        self.actions = actions if actions is not None else list(
            np.arange(config.RL_FREQ_RANGE_HZ[0], config.RL_FREQ_RANGE_HZ[1] + 1e-9, config.RL_FREQ_STEP_HZ)
        )
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.num_states = len(config.RL_STATE_BOUNDS) + 1
        self.q_table = np.zeros((self.num_states, len(self.actions)))
        self.profile_path = profile_path
        self.load_profile()

    def get_state_index(self, stress_index: float) -> int:
        if stress_index < config.RL_STATE_BOUNDS[0]:
            return 0
        if stress_index <= config.RL_STATE_BOUNDS[1]:
            return 1
        if stress_index <= config.RL_STATE_BOUNDS[2]:
            return 2
        return 3

    def choose_frequency(self, current_stress: float) -> tuple[float, int, str]:
        state_idx = self.get_state_index(current_stress)
        if random.uniform(0, 1) < self.epsilon:
            action_idx = random.randint(0, len(self.actions) - 1)
            strategy = "Разведка нового био-резонанса"
        else:
            action_idx = int(np.argmax(self.q_table[state_idx]))
            strategy = "Оптимальный личный паттерн"
        return self.actions[action_idx], action_idx, strategy

    def learn(self, old_stress: float, action_idx: int, new_stress: float, rmssd_growth: float) -> None:
        old_state = self.get_state_index(old_stress)
        new_state = self.get_state_index(new_stress)
        stress_delta = old_stress - new_stress
        reward = stress_delta + (rmssd_growth * 2)
        if stress_delta < 0:
            reward -= 50
        old_q = self.q_table[old_state, action_idx]
        max_future_q = float(np.max(self.q_table[new_state]))
        self.q_table[old_state, action_idx] = old_q + self.alpha * (
            reward + self.gamma * max_future_q - old_q
        )

    def save_profile(self) -> None:
        data = {"q_table": self.q_table.tolist(), "actions": self.actions}
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def load_profile(self) -> None:
        if not self.profile_path.exists():
            return
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded_table = np.array(data["q_table"])
            # Валидация: размерность должна совпадать
            if loaded_table.shape != (self.num_states, len(self.actions)):
                import logging
                log = logging.getLogger(__name__)
                log.warning(
                    "Q-table shape mismatch: expected %s, got %s — resetting",
                    (self.num_states, len(self.actions)),
                    loaded_table.shape,
                )
                return
            # Валидация: нет NaN / Inf
            if not np.all(np.isfinite(loaded_table)):
                import logging
                log = logging.getLogger(__name__)
                log.warning("Q-table contains NaN/Inf — resetting")
                return
            self.q_table = loaded_table
        except (json.JSONDecodeError, KeyError, OSError):
            import logging
            log = logging.getLogger(__name__)
            log.warning("Corrupted brain profile — starting fresh")
