"""Writer Deck — distraction-free e-ink writing device."""

import atexit
import logging
import logging.handlers
import os
import sys
import traceback
from pathlib import Path

# Ensure lib/ (waveshare_epd) is on the path regardless of how the app is launched
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from writerdeck.core.app import App
from writerdeck.core.config import load_config


def _setup_logging(log_dir: str) -> None:
    """Configure logging with RotatingFileHandler + stream handler."""
    log_path = Path(os.path.expanduser(log_dir))
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "writerdeck.log"

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=512 * 1024, backupCount=3,
    )
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def main() -> None:
    config = load_config()
    log_dir = config.get("log_dir", "~/.config/writer-deck/logs")
    _setup_logging(log_dir)

    app = App()
    # Belt-and-suspenders: deep-sleep the panel on any interpreter exit path,
    # even one that bypasses the signal handler / emergency_save. close() is
    # idempotent, so running it here plus in _do_shutdown is safe.
    atexit.register(app._driver.close)
    try:
        app.run()
    except KeyboardInterrupt:
        app.emergency_save()
        _best_effort_cleanup(app)
    except Exception:
        logging.critical("Unhandled exception:\n%s", traceback.format_exc())
        app.emergency_save()
        _best_effort_cleanup(app)

    logging.info("Writer Deck exited.")
    sys.exit(0)


def _best_effort_cleanup(app: App) -> None:
    """Run shutdown cleanup on the error/interrupt paths.

    run() only reaches its own _do_shutdown() when the main loop exits
    normally; if it raises (or KeyboardInterrupt fires) that never runs, so a
    StdinReader would leave the terminal in raw-tty mode. Restore the terminal
    / stop the reader here. Best-effort: never raises, never masks the original
    error path. emergency_save() has already persisted the document.
    """
    try:
        app._do_shutdown()
    except Exception:
        # _do_shutdown() failed partway — at minimum stop the keyboard reader
        # so raw-tty mode is restored.
        try:
            app._keyboard.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
