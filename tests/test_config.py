"""Tests for config validation, deep merge, Config properties, and load_config."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from writerdeck.core.config import _validate, _deep_merge, Config


class TestValidation:
    def test_valid_config(self):
        data = {
            "display_model": "epd7in5_V2",
            "font_family": "Hack",
            "font_size": 14,
        }
        warnings = _validate(data)
        assert warnings == []

    def test_unknown_key(self):
        data = {"unknown_key": "value"}
        warnings = _validate(data)
        assert len(warnings) == 1
        assert "Unknown config key" in warnings[0]

    def test_wrong_type(self):
        data = {"font_size": "not_a_number"}
        warnings = _validate(data)
        assert len(warnings) == 1
        assert "expected" in warnings[0]

    def test_out_of_range(self):
        data = {"font_size": 200}
        warnings = _validate(data)
        assert len(warnings) == 1
        assert "out of range" in warnings[0]

    def test_in_range(self):
        data = {"font_size": 16}
        warnings = _validate(data)
        assert warnings == []

    def test_multiple_errors(self):
        data = {
            "unknown_key": "val",
            "font_size": "bad",
            "render_interval_ms": 1,  # below range min=50
        }
        warnings = _validate(data)
        assert len(warnings) == 3

    def test_boolean_field(self):
        data = {"enable_battery_monitor": True}
        warnings = _validate(data)
        assert warnings == []

    def test_boolean_wrong_type(self):
        data = {"enable_battery_monitor": "yes"}
        warnings = _validate(data)
        assert len(warnings) == 1

    def test_list_field(self):
        data = {"mode_order": ["distraction_free"]}
        warnings = _validate(data)
        assert warnings == []

    def test_dict_field(self):
        data = {"sleep_tiers": {"display_off_minutes": 5}}
        warnings = _validate(data)
        assert warnings == []

    def test_new_panel_safety_keys_valid(self):
        data = {
            "display_idle_sleep_seconds": 20,
            "full_refresh_max_seconds": 300,
        }
        assert _validate(data) == []

    def test_boundary_values(self):
        data = {"font_size": 6}  # min boundary
        assert _validate(data) == []
        data = {"font_size": 72}  # max boundary
        assert _validate(data) == []

    def test_float_accepted_for_int_field(self):
        data = {"font_size": 14.0}
        assert _validate(data) == []


class TestDeepMerge:
    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_dict_merge(self):
        base = {"outer": {"a": 1, "b": 2}}
        override = {"outer": {"b": 3, "c": 4}}
        result = _deep_merge(base, override)
        assert result == {"outer": {"a": 1, "b": 3, "c": 4}}

    def test_override_replaces_non_dict(self):
        base = {"key": "old"}
        override = {"key": "new"}
        result = _deep_merge(base, override)
        assert result == {"key": "new"}

    def test_list_replaced_not_appended(self):
        base = {"modes": ["a", "b"]}
        override = {"modes": ["c"]}
        result = _deep_merge(base, override)
        assert result == {"modes": ["c"]}

    def test_empty_override(self):
        base = {"a": 1, "b": 2}
        result = _deep_merge(base, {})
        assert result == {"a": 1, "b": 2}

    def test_empty_base(self):
        result = _deep_merge({}, {"a": 1})
        assert result == {"a": 1}

    def test_deeply_nested(self):
        base = {"l1": {"l2": {"l3": "old"}}}
        override = {"l1": {"l2": {"l3": "new"}}}
        result = _deep_merge(base, override)
        assert result == {"l1": {"l2": {"l3": "new"}}}

    def test_preserves_sibling_keys(self):
        base = {"parent": {"keep": "yes", "change": "old"}}
        override = {"parent": {"change": "new"}}
        result = _deep_merge(base, override)
        assert result["parent"]["keep"] == "yes"
        assert result["parent"]["change"] == "new"

    def test_does_not_mutate_base(self):
        base = {"a": {"b": 1}}
        override = {"a": {"b": 2}}
        _deep_merge(base, override)
        assert base == {"a": {"b": 1}}

    def test_override_dict_over_non_dict(self):
        base = {"key": "string"}
        override = {"key": {"nested": True}}
        result = _deep_merge(base, override)
        assert result == {"key": {"nested": True}}


class TestConfigProperties:
    def _config(self, **overrides):
        data = {
            "display_model": "epd7in5_V2",
            "font_family": "Hack",
            "font_size": 14,
            "daily_goal_words": 500,
            "partial_refresh_max_streak": 20,
            "render_interval_ms": 500,
            "idle_full_refresh_seconds": 10,
            "display_sleep_minutes": 5,
            "keyboard_device": "auto",
            "keyboard_input": "auto",
            "mode_order": ["distraction_free", "dashboard"],
            "documents_dir": "~/Documents/writer-deck",
            "autosave_interval_seconds": 90,
            "battery_warning_percent": 15,
            "battery_shutdown_percent": 3,
            "enable_battery_monitor": True,
            "pisugar_socket": "/tmp/pisugar-server.sock",
            "show_title_bar": True,
            "default_format": "txt",
            "sleep_tiers": {"display_off_minutes": 5},
        }
        data.update(overrides)
        return Config(data)

    def test_display_model(self):
        assert self._config().display_model == "epd7in5_V2"

    def test_font_family(self):
        assert self._config().font_family == "Hack"

    def test_font_size_returns_int(self):
        c = self._config(font_size=14.0)
        assert c.font_size == 14
        assert isinstance(c.font_size, int)

    def test_daily_goal_words(self):
        assert self._config().daily_goal_words == 500

    def test_partial_refresh_max_streak(self):
        assert self._config().partial_refresh_max_streak == 20

    def test_render_interval_ms(self):
        assert self._config().render_interval_ms == 500

    def test_idle_full_refresh_seconds(self):
        assert self._config().idle_full_refresh_seconds == 10

    def test_full_refresh_max_seconds_default(self):
        c = Config({"display_model": "x"})
        assert c.full_refresh_max_seconds == 300

    def test_full_refresh_max_seconds_override(self):
        c = self._config(full_refresh_max_seconds=120)
        assert c.full_refresh_max_seconds == 120

    def test_display_sleep_minutes(self):
        assert self._config().display_sleep_minutes == 5

    def test_display_idle_sleep_seconds_default(self):
        c = Config({"display_model": "x"})
        assert c.display_idle_sleep_seconds == 20

    def test_display_idle_sleep_seconds_override(self):
        c = self._config(display_idle_sleep_seconds=45)
        assert c.display_idle_sleep_seconds == 45

    def test_keyboard_device(self):
        assert self._config().keyboard_device == "auto"

    def test_keyboard_input(self):
        assert self._config().keyboard_input == "auto"

    def test_keyboard_input_default(self):
        c = Config({"display_model": "x"})
        assert c.keyboard_input == "auto"

    def test_mode_order_returns_list(self):
        c = self._config()
        assert c.mode_order == ["distraction_free", "dashboard"]
        # Should be a copy
        c.mode_order.append("typewriter")
        assert c.mode_order == ["distraction_free", "dashboard"]

    def test_documents_dir_expands_tilde(self):
        c = self._config()
        assert "~" not in str(c.documents_dir)
        assert isinstance(c.documents_dir, Path)

    def test_autosave_interval_seconds(self):
        assert self._config().autosave_interval_seconds == 90

    def test_battery_warning_percent(self):
        assert self._config().battery_warning_percent == 15

    def test_battery_shutdown_percent(self):
        assert self._config().battery_shutdown_percent == 3

    def test_enable_battery_monitor(self):
        assert self._config().enable_battery_monitor is True

    def test_pisugar_socket(self):
        assert self._config().pisugar_socket == "/tmp/pisugar-server.sock"

    def test_show_title_bar(self):
        assert self._config().show_title_bar is True

    def test_show_title_bar_default(self):
        c = Config({"display_model": "x"})
        assert c.show_title_bar is True

    def test_default_format(self):
        assert self._config().default_format == "txt"

    def test_default_format_default(self):
        c = Config({"display_model": "x"})
        assert c.default_format == "txt"

    def test_sleep_tiers(self):
        c = self._config()
        assert c.sleep_tiers == {"display_off_minutes": 5}

    def test_sleep_tiers_default(self):
        c = Config({"display_model": "x"})
        tiers = c.sleep_tiers
        assert "display_off_minutes" in tiers
        assert "cpu_powersave_minutes" in tiers

    def test_get_existing_key(self):
        assert self._config().get("font_family") == "Hack"

    def test_get_missing_key_with_default(self):
        assert self._config().get("nonexistent", 42) == 42

    def test_get_missing_key_no_default(self):
        assert self._config().get("nonexistent") is None


class TestLoadConfig:
    def test_load_default_config(self, tmp_path):
        """Test loading config from a custom project root."""
        import writerdeck.core.config as config_module

        # Save and restore singleton
        old_instance = config_module._instance
        config_module._instance = None
        try:
            from writerdeck.core.config import load_config
            # Use the actual project root
            project_root = Path(__file__).resolve().parent.parent
            cfg = load_config(project_root=project_root)
            assert cfg.display_model == "epd7in5_V2"
            assert cfg.font_family == "Hack"
            assert cfg.font_size == 14
        finally:
            config_module._instance = old_instance

    def test_load_with_user_override(self, tmp_path):
        """Test that user config.yaml overrides defaults."""
        import yaml
        import writerdeck.core.config as config_module

        old_instance = config_module._instance
        config_module._instance = None
        try:
            # Write a minimal default config
            default = {
                "display_model": "epd7in5_V2",
                "font_family": "Hack",
                "font_size": 14,
            }
            (tmp_path / "config_default.yaml").write_text(yaml.dump(default))
            # Write user override
            override = {"font_size": 20}
            (tmp_path / "config.yaml").write_text(yaml.dump(override))

            from writerdeck.core.config import load_config
            cfg = load_config(project_root=tmp_path)
            assert cfg.font_size == 20
            assert cfg.font_family == "Hack"  # not overridden
        finally:
            config_module._instance = old_instance
