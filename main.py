"""Writer Deck — distraction-free e-ink writing device."""

import logging
import logging.handlers
import os
import sys
import traceback
from pathlib import Path

# Ensure lib/ (waveshare_epd) is on the path regardless of how the app is launched
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from writerdeck.core.config import load_config
from writerdeck.core.app import App


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
    try:
        app.run()
    except KeyboardInterrupt:
        app.emergency_save()
    except Exception:
        logging.critical("Unhandled exception:\n%s", traceback.format_exc())
        app.emergency_save()

    logging.info("Writer Deck exited.")
    sys.exit(0)


if __name__ == "__main__":
    main()
