# Writer Deck — Developer Tooling Improvements

All 5 improvements have been implemented.

---

## 1. Pygame Desktop Emulator — DONE

**What:** Live 800x480 window that emulates the e-ink display with interactive keyboard input.

**Files created:**
- `writerdeck/display/pygame_driver.py` — `PygameDriver` implementing `DisplayDriver` protocol
- `writerdeck/input/pygame_reader.py` — `PygameKeyboardReader` with `poll()` method and pygame-to-evdev keycode mapping

**Files modified:**
- `writerdeck/core/app.py` — pygame branch in `__init__`, `poll()` call in main loop, `close()` in shutdown
- `config_default.yaml` — documents `pygame` as a `keyboard_input` option

**Design:** Reuses `KeyMapper` entirely (pygame keycodes -> evdev scancodes). `poll()` runs on main thread (macOS compatible). Optional dependency — guarded import.

**Activate:** `keyboard_input: pygame` in config.yaml

---

## 2. pytest-cov — DONE

**What:** Coverage reporting for the 200+ existing tests.

**Configuration:** `pyproject.toml` — `[tool.pytest.ini_options]`, `[tool.coverage.*]` sections

**Usage:** Just run `pytest` — coverage runs automatically. Terminal shows missing lines, `htmlcov/index.html` has a browsable report.

---

## 3. mypy Static Type Checking — DONE

**What:** Catch type errors across the codebase. Leverages existing `from __future__ import annotations` and type hints.

**Configuration:** `pyproject.toml` — `[tool.mypy]` section. Ignores missing imports for hardware deps (evdev, spidev, pisugar, waveshare, pygame). Excludes `lib/`, `venv/`, `tests/`.

**Usage:** `mypy writerdeck/`

---

## 4. ruff Linter + Formatter — DONE

**What:** Fast linter and formatter. Replaces flake8, isort, black in a single tool.

**Configuration:** `pyproject.toml` — `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.format]` sections. Rules: E, F, W, I (isort), UP (pyupgrade), B (bugbear), SIM (simplify). Line length 99, Python 3.12.

**Usage:**
- `ruff check writerdeck/ tests/` — lint
- `ruff check --fix writerdeck/ tests/` — auto-fix
- `ruff format writerdeck/ tests/` — format

---

## 5. rsync Deploy Script — DONE

**What:** One-command deployment to the Raspberry Pi over SSH.

**File created:** `deploy.sh` — rsync + service restart + log tail

**Usage:**
- `./deploy.sh` — defaults to `pi@writerdeck.local`
- `./deploy.sh 192.168.1.50` — custom host
- `./deploy.sh 192.168.1.50 myuser` — custom host and user

---

## Dev Dependencies

All tools are in `requirements-dev.txt`:
```
-r requirements.txt
pygame>=2.5.0
pytest>=7.0.0
pytest-cov>=4.0.0
mypy>=1.8.0
ruff>=0.3.0
```

Install with: `pip install -r requirements-dev.txt`
