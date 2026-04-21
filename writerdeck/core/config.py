"""Configuration loader — deep-merges config_default.yaml with user config.yaml."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_instance: Config | None = None

# Schema: key -> (expected types, optional (min, max) range)
_SCHEMA: dict[str, tuple[tuple[type, ...], tuple[Any, Any] | None]] = {
    "display_model": ((str,), None),
    "font_family": ((str,), None),
    "font_size": ((int, float), (6, 72)),
    "daily_goal_words": ((int, float), (0, 100000)),
    "partial_refresh_max_streak": ((int, float), (1, 1000)),
    "render_interval_ms": ((int, float), (50, 10000)),
    "idle_full_refresh_seconds": ((int, float), (1, 600)),
    "display_sleep_minutes": ((int, float), (0, 1440)),
    "keyboard_device": ((str,), None),
    "keyboard_input": ((str,), None),
    "mode_order": ((list,), None),
    "documents_dir": ((str,), None),
    "autosave_interval_seconds": ((int, float), (10, 3600)),
    "battery_warning_percent": ((int, float), (1, 100)),
    "battery_shutdown_percent": ((int, float), (1, 100)),
    "enable_battery_monitor": ((bool,), None),
    "pisugar_socket": ((str,), None),
    "log_dir": ((str,), None),
    "show_title_bar": ((bool,), None),
    "default_format": ((str,), None),
    "idle_deep_clean_seconds": ((int, float), (0, 86400)),
    "sleep_tiers": ((dict,), None),
}


def _validate(data: dict[str, Any]) -> list[str]:
    """Validate config data. Returns list of warning messages."""
    warnings: list[str] = []
    for key, value in data.items():
        if key not in _SCHEMA:
            warnings.append(f"Unknown config key: {key!r}")
            continue
        expected_types, value_range = _SCHEMA[key]
        if not isinstance(value, expected_types):
            warnings.append(
                f"Config key {key!r}: expected {expected_types}, got {type(value).__name__}"
            )
            continue
        if value_range is not None and isinstance(value, (int, float)):
            lo, hi = value_range
            if not (lo <= value <= hi):
                warnings.append(
                    f"Config key {key!r}: value {value} out of range [{lo}, {hi}]"
                )
    return warnings


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class Config:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    # -- Typed accessors --------------------------------------------------

    @property
    def display_model(self) -> str:
        return self._data["display_model"]

    @property
    def font_family(self) -> str:
        return self._data["font_family"]

    @property
    def font_size(self) -> int:
        return int(self._data["font_size"])

    @property
    def daily_goal_words(self) -> int:
        return int(self._data["daily_goal_words"])

    @property
    def partial_refresh_max_streak(self) -> int:
        return int(self._data["partial_refresh_max_streak"])

    @property
    def render_interval_ms(self) -> int:
        return int(self._data["render_interval_ms"])

    @property
    def idle_full_refresh_seconds(self) -> int:
        return int(self._data["idle_full_refresh_seconds"])

    @property
    def display_sleep_minutes(self) -> int:
        return int(self._data["display_sleep_minutes"])

    @property
    def keyboard_device(self) -> str:
        return self._data["keyboard_device"]

    @property
    def keyboard_input(self) -> str:
        return self._data.get("keyboard_input", "auto")

    @property
    def mode_order(self) -> list[str]:
        return list(self._data["mode_order"])

    @property
    def documents_dir(self) -> Path:
        return Path(os.path.expanduser(self._data["documents_dir"]))

    @property
    def autosave_interval_seconds(self) -> int:
        return int(self._data["autosave_interval_seconds"])

    @property
    def battery_warning_percent(self) -> int:
        return int(self._data["battery_warning_percent"])

    @property
    def battery_shutdown_percent(self) -> int:
        return int(self._data["battery_shutdown_percent"])

    @property
    def enable_battery_monitor(self) -> bool:
        return bool(self._data["enable_battery_monitor"])

    @property
    def pisugar_socket(self) -> str:
        return self._data["pisugar_socket"]

    @property
    def show_title_bar(self) -> bool:
        return bool(self._data.get("show_title_bar", True))

    @property
    def default_format(self) -> str:
        return self._data.get("default_format", "txt")


    @property
    def idle_deep_clean_seconds(self) -> int:
        return int(self._data.get("idle_deep_clean_seconds", 300))

    @property
    def sleep_tiers(self) -> dict:
        return self._data.get("sleep_tiers", {
            "display_off_minutes": 5,
            "cpu_powersave_minutes": 15,
            "system_suspend_minutes": 30,
        })

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


def load_config(project_root: Path | None = None) -> Config:
    """Load and merge configuration, returning a singleton Config instance."""
    global _instance
    if _instance is not None:
        return _instance

    root = project_root or _PROJECT_ROOT
    default_path = root / "config_default.yaml"
    user_path = root / "config.yaml"

    with open(default_path) as f:
        data = yaml.safe_load(f) or {}

    if user_path.exists():
        with open(user_path) as f:
            overrides = yaml.safe_load(f) or {}
        data = _deep_merge(data, overrides)

    # Validate and log warnings
    warnings = _validate(data)
    for w in warnings:
        logger.warning("Config: %s", w)

    _instance = Config(data)
    return _instance


def get_config() -> Config:
    """Return the singleton Config, loading defaults if necessary."""
    if _instance is None:
        return load_config()
    return _instance
