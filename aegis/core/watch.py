"""Буфер данных Galaxy Watch / Wear OS для контура AegisNeuro."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any


MIN_VALID_RR_MS = 300
MAX_VALID_RR_MS = 2000
MIN_VALID_BPM = 35
MAX_VALID_BPM = 220


@dataclass
class WatchDataBuffer:
    """Хранит валидированные HR/IBI данные, приходящие с часов."""

    max_rr_intervals: int = 180
    stale_after_sec: float = 15.0
    rr_intervals_ms: list[int] = field(default_factory=list)
    heart_rate_bpm: int | None = None
    quality: str = "unknown"
    source: str = "watch"
    last_seen_monotonic: float | None = None
    rejected_samples: int = 0

    def ingest(self, payload: dict[str, Any]) -> int:
        """Принять пакет от Wear OS/Data Layer и вернуть число новых R-R интервалов."""

        self.last_seen_monotonic = time.monotonic()
        self.source = str(payload.get("source") or self.source or "watch")
        self.quality = str(payload.get("quality") or payload.get("signal_quality") or self.quality)

        bpm = payload.get("heart_rate_bpm", payload.get("bpm"))
        if bpm is not None:
            parsed_bpm = self._parse_int(bpm)
            if parsed_bpm is not None and MIN_VALID_BPM <= parsed_bpm <= MAX_VALID_BPM:
                self.heart_rate_bpm = parsed_bpm
            else:
                self.rejected_samples += 1

        intervals = self._extract_intervals(payload)
        accepted = 0
        for interval in intervals:
            parsed_interval = self._parse_int(interval)
            if parsed_interval is None:
                self.rejected_samples += 1
                continue
            if MIN_VALID_RR_MS <= parsed_interval <= MAX_VALID_RR_MS:
                self.rr_intervals_ms.append(parsed_interval)
                accepted += 1
            else:
                self.rejected_samples += 1

        if len(self.rr_intervals_ms) > self.max_rr_intervals:
            self.rr_intervals_ms = self.rr_intervals_ms[-self.max_rr_intervals :]

        return accepted

    def latest_rr_intervals(self) -> list[int]:
        return list(self.rr_intervals_ms)

    def has_enough_hrv_data(self, minimum: int = 10) -> bool:
        return len(self.rr_intervals_ms) >= minimum

    def is_connected(self) -> bool:
        if self.last_seen_monotonic is None:
            return False
        return (time.monotonic() - self.last_seen_monotonic) <= self.stale_after_sec

    def summary(self) -> dict[str, Any]:
        return {
            "connected": self.is_connected(),
            "heart_rate_bpm": self.heart_rate_bpm,
            "rr_count": len(self.rr_intervals_ms),
            "quality": self.quality,
            "source": self.source,
            "rejected_samples": self.rejected_samples,
        }

    def reset(self) -> None:
        self.rr_intervals_ms.clear()
        self.heart_rate_bpm = None
        self.quality = "unknown"
        self.last_seen_monotonic = None
        self.rejected_samples = 0

    def _extract_intervals(self, payload: dict[str, Any]) -> list[Any]:
        for key in ("rr_intervals_ms", "ibi_ms", "rr_ms", "ibi"):
            value = payload.get(key)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                return list(value)
            return [value]
        return []

    def _parse_int(self, value: Any) -> int | None:
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None
