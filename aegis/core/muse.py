"""Менеджер Muse 2 EEG через BrainFlow.

Источник: инлайн-копии из ``aegis_neuro_system.py`` и
``aegis_neuro_gui.py``. Объединены лучшие стороны обеих версий:
- подробные сообщения об ошибках (из GUI-копии)
- обновление статуса при остановке (из system-копии)
"""

from __future__ import annotations

import logging
import threading
import time

import numpy as np

log = logging.getLogger(__name__)

try:
    import brainflow
    from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
    from brainflow.data_filter import DataFilter, DetrendOperations, FilterTypes
    BRAINFLOW_AVAILABLE = True
except ImportError:
    BRAINFLOW_AVAILABLE = False


class MuseHardwareManager:
    def __init__(self) -> None:
        self.is_running: bool = False
        self.board: BoardShim | None = None
        self.eeg_channels: list[int] = []
        self.sampling_rate: int = 256
        self.current_alpha_power: float = 0.5
        self.hardware_status: str = "Отключено (Режим симуляции)"
        self._worker_thread: threading.Thread | None = None

    def start_stream(self) -> bool:
        if not BRAINFLOW_AVAILABLE:
            self.hardware_status = "Внимание: библиотека brainflow не установлена. Демо-режим."
            log.warning("brainflow не установлен — запуск в демо-режиме")
            return False
        try:
            params = BrainFlowInputParams()
            board_id = BoardIds.MUSE_2_BOARD.value
            self.board = BoardShim(board_id, params)
            self.board.prepare_session()
            self.board.start_stream()
            self.eeg_channels = BoardShim.get_eeg_channels(board_id)
            self.sampling_rate = BoardShim.get_sampling_rate(board_id)
            self.is_running = True
            self.hardware_status = "Muse 2 подключена [Поток RAW ЭЭГ]"
            log.info("Muse 2 поток запущен")
            self._worker_thread = threading.Thread(target=self._update_data_loop, daemon=True)
            self._worker_thread.start()
            return True
        except Exception as exc:
            self.hardware_status = f"Ошибка BLE: {exc}"
            self.is_running = False
            log.error("Muse 2 BLE ошибка: %s", exc)
            return False

    def _update_data_loop(self) -> None:
        while self.is_running:
            try:
                time.sleep(0.5)
                data = self.board.get_current_board_data(512)
                if data.shape[1] < 256:
                    continue
                alpha_levels: list[float] = []
                for channel in self.eeg_channels:
                    channel_data = data[channel]
                    DataFilter.detrend(channel_data, DetrendOperations.CONSTANT.value)
                    nfft = DataFilter.get_nearest_power_of_two(self.sampling_rate)
                    psd = DataFilter.get_custom_psd(
                        channel_data, self.sampling_rate, nfft, FilterTypes.BLACKMAN_HARRIS.value
                    )
                    alpha_band = DataFilter.get_band_power(psd, 8.0, 12.0)
                    alpha_levels.append(alpha_band)
                raw_alpha = sum(alpha_levels) / len(alpha_levels) if alpha_levels else 0
                self.current_alpha_power = min(max(raw_alpha / 20.0, 0.05), 1.0)
            except Exception as exc:
                log.debug("Muse data tick error: %s", exc)

    def stop_stream(self) -> None:
        self.is_running = False
        if self.board is not None:
            try:
                if self.board.is_prepared():
                    self.board.stop_stream()
                    self.board.release_session()
                self.hardware_status = "Сессия Muse 2 успешно завершена."
                log.info("Muse 2 поток остановлен")
            except Exception as exc:
                log.warning("Muse 2 ошибка при остановке: %s", exc)
                self.hardware_status = f"Ошибка остановки Muse: {exc}"