"""App orchestrator — owns all subsystems, runs the main event loop."""

from __future__ import annotations

import logging
import os
import queue
import signal
import socket
import threading
import time
from typing import TYPE_CHECKING

from writerdeck.core.config import get_config
from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.display.driver import create_driver, DisplayDriver
from writerdeck.display.refresh_manager import RefreshManager
from writerdeck.display.renderer import render
from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import BaseMode
from writerdeck.modes.dashboard import DashboardMode
from writerdeck.modes.distraction_free import DistractionFreeMode
from writerdeck.modes.typewriter import TypewriterMode
from writerdeck.utils.file_manager import FileManager
from writerdeck.utils.platform import detect_platform
from writerdeck.utils.power import Power
from writerdeck.utils.usb_export import find_usb_mount, export_documents

logger = logging.getLogger(__name__)


class App:
    def __init__(self) -> None:
        self._config = get_config()
        self._hw = detect_platform()
        self._running = False

        # Display
        self._driver: DisplayDriver = create_driver(use_null=not self._hw.is_pi)
        self._refresh = RefreshManager(
            max_streak=self._config.partial_refresh_max_streak,
            idle_full_seconds=self._config.idle_full_refresh_seconds,
        )

        # Document & session
        self._doc = Document()
        self._session = Session(daily_goal=self._config.daily_goal_words)
        self._file_mgr = FileManager(
            self._config.documents_dir,
            self._config.autosave_interval_seconds,
        )

        # Status bar
        from writerdeck.display.status_bar import StatusBar
        self._status = StatusBar()

        # Input — choose reader based on config
        self._last_keypress = time.monotonic()
        self._display_sleeping = False
        keyboard_input = self._config.keyboard_input

        if keyboard_input == "pygame":
            from writerdeck.display.pygame_driver import PygameDriver
            from writerdeck.input.pygame_reader import PygameKeyboardReader
            self._driver = PygameDriver()
            self._keyboard = PygameKeyboardReader(on_any_key=self._on_any_key)
        elif keyboard_input == "stdin" or (keyboard_input == "auto" and not self._hw.is_pi):
            from writerdeck.input.stdin_reader import StdinReader
            self._keyboard = StdinReader(on_any_key=self._on_any_key)
        else:
            from writerdeck.input.keyboard import KeyboardReader
            self._keyboard = KeyboardReader(
                device_path=self._config.keyboard_device,
                on_any_key=self._on_any_key,
            )

        # Modes
        self._modes = self._build_modes()
        self._mode_idx = 0
        self._mode: BaseMode = self._modes[0]

        # Overlay (font picker, file picker, find/replace)
        self._overlay = None

        # Power
        self._power = Power(
            socket_path=self._config.pisugar_socket,
            warning_pct=self._config.battery_warning_percent,
            shutdown_pct=self._config.battery_shutdown_percent,
            enabled=self._config.enable_battery_monitor,
        )

        # Sleep tiers state
        self._tier2_active = False
        self._tier3_active = False
        self._needs_display_wake = False  # set by _on_any_key; handled on main thread

        # Wakeup event — set by _on_any_key() to interrupt the loop's idle sleep
        self._wakeup = threading.Event()

    def _build_modes(self) -> list[BaseMode]:
        font = self._config.font_family
        size = self._config.font_size
        mode_map: dict[str, BaseMode] = {
            "distraction_free": DistractionFreeMode(font_family=font, font_size=size),
            "dashboard": DashboardMode(font_family=font, font_size=size),
            "typewriter": TypewriterMode(font_family=font, font_size=size),
        }
        return [mode_map[name] for name in self._config.mode_order if name in mode_map]

    def run(self) -> None:
        self._running = True
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        # Init driver if not already done
        if not self._hw.is_pi:
            self._driver.init()

        # Splash screen
        from writerdeck.display.splash import render_splash
        try:
            self._driver.display_full(render_splash())
        except Exception:
            pass

        # Start subsystems
        self._keyboard.start()
        self._power.start(shutdown_callback=self._emergency_shutdown)
        self._session.start(self._doc.word_count)

        # Load last opened doc, fall back to most recently modified, then create new
        name_to_load = self._file_mgr.load_last_open() or self._file_mgr.most_recent_document()
        if name_to_load:
            self._file_mgr.load(name_to_load, self._doc)
        else:
            name = self._file_mgr.new_document_name()
            self._doc.load("", name)
            self._file_mgr.save_last_open(name)

        self._mode.on_enter()
        self._render_and_refresh(force_full=True)

        logger.info(
            "Writer Deck running — platform=%s, mode=%s",
            self._hw.name, self._mode.name,
        )

        interval = self._hw.render_interval_ms / 1000.0
        tiers = self._config.sleep_tiers
        display_off_secs = tiers.get("display_off_minutes", 5) * 60
        cpu_save_secs = tiers.get("cpu_powersave_minutes", 15) * 60
        suspend_secs = tiers.get("system_suspend_minutes", 30) * 60

        while self._running:
            # Pump events for poll-based readers (e.g. PygameKeyboardReader)
            if hasattr(self._keyboard, "poll"):
                self._keyboard.poll()

            # Drain input queue in batch
            changed = False
            try:
                while True:
                    action, char = self._keyboard.queue.get_nowait()
                    changed |= self._handle_action(action, char)
            except queue.Empty:
                pass

            # Autosave check
            self._file_mgr.maybe_autosave(self._doc)

            # Sleep tier checks
            idle_secs = time.monotonic() - self._last_keypress

            # Tier 1: display sleep
            if (
                display_off_secs > 0
                and not self._display_sleeping
                and idle_secs > display_off_secs
            ):
                self._display_sleeping = True
                self._driver.sleep()
                logger.info("Display sleeping (idle)")

            # Tier 2: CPU powersave
            if (
                cpu_save_secs > 0
                and not self._tier2_active
                and idle_secs > cpu_save_secs
            ):
                self._enter_cpu_powersave()

            # Tier 3: system suspend
            if (
                suspend_secs > 0
                and not self._tier3_active
                and idle_secs > suspend_secs
            ):
                self._enter_system_suspend()

            # Render if something changed
            if changed and not self._display_sleeping:
                if self._needs_display_wake:
                    self._driver.wake()
                    self._needs_display_wake = False
                    logger.info("Display woken from sleep")
                self._render_and_refresh()

            # Watchdog
            self._notify_watchdog()

            self._wakeup.wait(timeout=interval)
            self._wakeup.clear()

        # Main loop exited — run cleanup once
        self._do_shutdown()

    def _handle_action(self, action: KeyAction, char: str) -> bool:
        # If overlay is active, route input there
        if self._overlay is not None:
            result = self._overlay.handle_input(action, char)
            if result is not None:
                self._handle_overlay_result(result)
                self._overlay = None
                self._refresh.request_full()
            return True

        if action == KeyAction.QUIT:
            self._shutdown()
            return False
        if action == KeyAction.SAVE:
            if not self._file_mgr._doc_path(self._doc.name).exists():
                from writerdeck.modes.save_name_overlay import SaveNameOverlay
                self._overlay = SaveNameOverlay(self._doc.name)
                self._refresh.request_full()
                return True
            self._file_mgr.save(self._doc)
            self._session.persist(self._doc.word_count)
            self._status.show("Saved")
            self._refresh.request_full()
            return True
        if action == KeyAction.SWITCH_MODE_NEXT:
            return self._switch_mode(1)
        if action == KeyAction.SWITCH_MODE_PREV:
            return self._switch_mode(-1)
        if action == KeyAction.NEW_DOC:
            self._file_mgr.force_autosave(self._doc)
            self._session.persist(self._doc.word_count)
            name = self._file_mgr.new_document_name()
            self._doc.load("", name)
            self._file_mgr.save_last_open(name)
            self._session.start(0)
            self._refresh.request_full()
            return True
        if action == KeyAction.OPEN_DOC:
            from writerdeck.modes.file_picker import FilePickerOverlay
            self._overlay = FilePickerOverlay(
                list_entries=self._file_mgr.list_entries,
                create_folder=self._file_mgr.create_folder,
                rename=self._file_mgr.rename,
                delete=self._file_mgr.delete,
            )
            self._refresh.request_full()
            return True
        if action == KeyAction.FIND:
            from writerdeck.modes.find_overlay import FindOverlay
            self._overlay = FindOverlay()
            self._refresh.request_full()
            return True
        if action == KeyAction.FONT_MENU:
            from writerdeck.modes.font_picker import FontPickerOverlay
            from writerdeck.display.fonts import list_available_fonts
            self._overlay = FontPickerOverlay(list_available_fonts())
            self._refresh.request_full()
            return True
        if action == KeyAction.EXPORT_USB:
            target = find_usb_mount()
            if target:
                count = export_documents(self._config.documents_dir, target)
                self._status.show(f"Exported {count} files to USB")
            else:
                self._status.show("No USB drive found")
            self._refresh.request_full()
            return True
        if action == KeyAction.ESCAPE:
            return False

        return self._mode.handle_input(action, char, self._doc)

    def _handle_overlay_result(self, result) -> None:
        """Process the result returned by an overlay on completion."""
        if result is None:
            return
        if isinstance(result, dict):
            if "open_doc" in result:
                name = result["open_doc"]
                self._file_mgr.force_autosave(self._doc)
                self._session.persist(self._doc.word_count)
                self._file_mgr.load(name, self._doc)
                self._file_mgr.save_last_open(name)
                self._session.start(self._doc.word_count)
            elif "save_as" in result:
                new_name = result["save_as"]
                self._doc.name = new_name
                self._file_mgr.save(self._doc)
                self._file_mgr.save_last_open(new_name)
                self._session.persist(self._doc.word_count)
                self._status.show("Saved")
                self._refresh.request_full()
            elif "renamed" in result:
                old = result["renamed"]["from"]
                new = result["renamed"]["to"]
                if self._doc.name == old:
                    self._doc.name = new
                from pathlib import Path as _Path
                self._status.show(f"Renamed to {_Path(new).name}")
            elif "deleted" in result:
                name = result["deleted"]
                if self._doc.name == name:
                    new_name = self._file_mgr.new_document_name()
                    self._doc.load("", new_name)
                    self._file_mgr.save_last_open(new_name)
                    self._session.start(0)
                self._status.show("Deleted")
            elif "font" in result:
                logger.info("Font changed to: %s", result["font"])
                # Rebuild modes with new font
                self._config._data["font_family"] = result["font"]
                self._modes = self._build_modes()
                self._mode = self._modes[self._mode_idx % len(self._modes)]
                self._mode.on_enter()
            elif "find" in result:
                query = result["find"]
                replace = result.get("replace")
                if replace is not None:
                    # Replace at current cursor
                    self._doc.replace_at(
                        self._doc.cursor_line, self._doc.cursor_col,
                        query, replace,
                    )
                    self._status.show("Replaced")
                else:
                    pos = self._doc.find_next(
                        query, self._doc.cursor_line, self._doc.cursor_col + 1,
                    )
                    if pos:
                        self._doc.cursor_line, self._doc.cursor_col = pos
                        self._status.show(f"Found at line {pos[0]+1}")
                    else:
                        self._status.show("Not found")

    def _switch_mode(self, direction: int) -> bool:
        self._mode.on_exit()
        self._mode_idx = (self._mode_idx + direction) % len(self._modes)
        self._mode = self._modes[self._mode_idx]
        self._mode.on_enter()
        self._refresh.request_full()
        logger.info("Switched to mode: %s", self._mode.name)
        return True

    def _render_and_refresh(self, force_full: bool = False) -> None:
        frame = self._mode.render(self._doc, self._session)

        # Inject title bar
        if self._config.show_title_bar:
            title = self._doc.name
            if self._doc.dirty:
                title += " *"
            frame.title = title

        # Inject status message
        msg = self._status.current
        if msg:
            frame.status_message = msg

        # Inject battery info for dashboard or when low
        if self._config.enable_battery_monitor and frame.stats is not None:
            if self._mode.name == "dashboard":
                frame.stats["Battery"] = self._power.battery_bar()
                # Add time estimate if available
                remaining = self._power.estimated_remaining_hours
                if remaining is not None:
                    hours = int(remaining)
                    minutes = int((remaining - hours) * 60)
                    frame.stats["Remaining"] = f"~{hours}h {minutes:02d}m"
            elif self._power.is_low:
                frame.stats["Battery"] = self._power.battery_bar()

        # Overlay rendering
        if self._overlay is not None:
            frame = self._overlay.render(frame)

        if force_full or frame.force_full_refresh:
            self._refresh.request_full()

        idle_secs = time.monotonic() - self._last_keypress
        will_full = self._refresh.should_full_refresh()

        # During active typing, suppress streak-triggered full refreshes so
        # rapid input doesn't cause 1-second interruptions.  Force and
        # idle-timer triggers still fire; ghosting is cleaned up when the
        # user pauses and the idle timer fires.
        if will_full and idle_secs < 2.0:
            will_full = self._refresh.should_full_refresh(ignore_streak=True)

        if will_full:
            deep_clean_threshold = self._config.idle_deep_clean_seconds
            is_deep_clean = deep_clean_threshold > 0 and idle_secs >= deep_clean_threshold

            if is_deep_clean:
                # User has been away long enough — do a GC16 clean to wipe
                # any accumulated ghosting. Uses init() waveform, not init_fast().
                image = render(frame, self._config.font_family, self._config.font_size)
                self._driver.display_clean(image)
            elif self._config.use_4gray:
                image = render(frame, self._config.font_family, self._config.font_size, grayscale=True)
                self._driver.display_full_4gray(image)
            else:
                image = render(frame, self._config.font_family, self._config.font_size)
                self._driver.display_full(image)
        else:
            image = render(frame, self._config.font_family, self._config.font_size)
            self._driver.display_partial(image)

        self._refresh.record_refresh(was_full=will_full)

    def _on_any_key(self) -> None:
        self._wakeup.set()
        self._last_keypress = time.monotonic()
        if self._display_sleeping:
            # Don't touch the display driver here — we're on the keyboard
            # background thread and EPD SPI is not thread-safe.  Signal the
            # main thread to call wake() before the next render.
            self._display_sleeping = False
            self._needs_display_wake = True
            self._refresh.request_full()
        # Reverse sleep tiers
        if self._tier2_active:
            self._exit_cpu_powersave()
        if self._tier3_active:
            self._tier3_active = False

    # -- Sleep tiers -------------------------------------------------------

    def _enter_cpu_powersave(self) -> None:
        try:
            gov_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
            if os.path.exists(gov_path):
                with open(gov_path, "w") as f:
                    f.write("powersave")
                self._tier2_active = True
                logger.info("CPU governor set to powersave")
        except Exception as e:
            logger.debug("Cannot set CPU governor: %s", e)

    def _exit_cpu_powersave(self) -> None:
        try:
            gov_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
            if os.path.exists(gov_path):
                with open(gov_path, "w") as f:
                    f.write("ondemand")
                logger.info("CPU governor set to ondemand")
        except Exception:
            pass
        self._tier2_active = False

    def _enter_system_suspend(self) -> None:
        self._tier3_active = True
        logger.info("Entering system suspend")
        try:
            os.system("systemctl suspend")
        except Exception:
            pass

    # -- Watchdog ----------------------------------------------------------

    def _notify_watchdog(self) -> None:
        """Send WATCHDOG=1 to systemd if NOTIFY_SOCKET is set."""
        notify_socket = os.environ.get("NOTIFY_SOCKET")
        if not notify_socket:
            return
        try:
            addr = notify_socket
            if addr.startswith("@"):
                addr = "\0" + addr[1:]
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.sendto(b"WATCHDOG=1", addr)
            sock.close()
        except Exception:
            pass

    # -- Emergency / Shutdown ----------------------------------------------

    def emergency_save(self) -> None:
        """Best-effort save of all state. Never raises."""
        try:
            self._file_mgr.force_autosave(self._doc)
        except Exception:
            pass
        try:
            self._session.persist(self._doc.word_count)
        except Exception:
            pass
        try:
            self._driver.sleep()
        except Exception:
            pass

    def _emergency_shutdown(self) -> None:
        logger.warning("Emergency shutdown — autosaving")
        self.emergency_save()

    def _shutdown(self) -> None:
        """Request a clean shutdown — safe to call from anywhere."""
        self._running = False

    def _do_shutdown(self) -> None:
        """Perform actual cleanup after the main loop exits. Called once."""
        logger.info("Shutting down")
        self._keyboard.stop()
        self._power.stop()
        self._file_mgr.force_autosave(self._doc)
        self._session.persist(self._doc.word_count)
        self._driver.close()  # close() calls sleep() internally

    def _signal_handler(self, signum, frame) -> None:
        self._running = False  # just set flag — cleanup runs after the loop exits
