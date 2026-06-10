"""Пути к runtime-данным и общие настройки пайплайна."""

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

BRAIN_PROFILE_PATH = DATA_DIR / "brain_profile.json"
BASELINE_PATH = DATA_DIR / "historical_baseline.json"
LONGEVITY_HISTORY_PATH = DATA_DIR / "longevity_history.json"

# Аудио
CARRIER_FREQ_HZ = 200.0
SAMPLE_RATE = 44100
CHUNK_SIZE = 1024

# RL
RL_STATE_BOUNDS = (150.0, 300.0, 500.0)
RL_FREQ_RANGE_HZ = (4.0, 12.5)
RL_FREQ_STEP_HZ = 0.5
RL_ALPHA = 0.2
RL_GAMMA = 0.9
RL_EPSILON = 0.3
