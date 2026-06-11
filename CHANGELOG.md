# Changelog

All notable changes to AegisNeuro will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2025-06-11

### Changed
- **Consolidated codebase**: all duplicated classes (AegisRLBrain, StormPredictor,
  AICognitiveOrchestrator, MuseHardwareManager) now live in `aegis/core/`.
  Root-level files import from the package — zero copy-paste.
- **Medical defaults**: `endocrine_issues`, `pelvic_congestion`, `cardio_limitations`
  all default to `False` (previously `True` — dangerous assumption).
- **Amazon affiliate tag**: removed hardcoded `aegisneuro0c-20`, now reads from
  `AEGIS_AMAZON_TAG` environment variable.
- **Q-table validation**: `load_profile()` now checks shape, NaN/Inf, and
  corrupted JSON — resets to zeros instead of crashing.
- **Logging**: replaced 121 `print()` calls with `logging` across all modules.
  Fixed 12 bare `except Exception: pass` blocks.
- **Buildozer**: removed `aegis/*` from `source.exclude_patterns` (package was
  excluded from APK!). Added BLE permissions for Android 12+.
- **CI/CD**: added `test` job (pytest) before Android build, Buildozer cache.

### Added
- `pyproject.toml` with `[build-system]`, dependencies, optional extras.
- `requirements.txt` for desktop.
- `.gitignore` (venv, .mypy_cache, .pytest_cache, etc.).
- `tests/test_core.py` — 31 tests covering DSP, RL brain, storm predictor,
  orchestrator, and marketplace.
- `aegis/core/orchestrator.py` — extracted from inline copies.
- `aegis/core/muse.py` — extracted from inline copies.
- `README.md`, `LICENSE` (MIT), `CHANGELOG.md`.