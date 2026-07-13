"""App orchestrator — owns all subsystems, runs the main event loop."""

from __future__ import annotations

import logging
import os
import queue
import signal
import socket
import threading
import time

from writerdeck.core.config import get_config
from writerdeck.core.document import Document
from writerdeck.core.session import Session
from writerdeck.display.driver import create_driver, DisplayDriver, DisplayError
from writerdeck.display.refresh_manager import RefreshManager
from writerdeck.display.renderer import render
from writerdeck.input.keymapper import KeyAction
from writerdeck.modes.base_mode import BaseMode
from writerdeck.modes.dashboard import DashboardMode
from writerdeck.modes.distraction_free import DistractionFreeMode
from writerdeck.modes.typewriter import TypewriterMode
from writerdeck.utils.file_manager import FileManager
from writerdeck.utils.perf import get_perf
from writerdeck.utils.platform import detect_platform
from writerdeck.utils.power import Power
from writerdeck.utils.usb_export import export_documents, find_usb_mount

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
            full_refresh_max_seconds=self._config.full_refresh_max_seconds,
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

        # PERF-1: last stats dict painted on a full refresh. On the per-keystroke
        # partial path we re-use this snapshot so the volatile Words/timer/sidebar
        # region renders identical bytes (no diff there → no repaint). Refreshed
        # values land on the next full/streak/idle refresh.
        self._stats_snapshot: dict[str, str] | None = None

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

        # FAULT-7: runtime headless/degraded state. If the panel fails repeatedly
        # at runtime (DisplayError from the FAULT-6 retry path), we stop touching
        # it but KEEP the main loop running — input drain, autosave and session
        # persist continue so the user's words are never lost. The panel is
        # retried every _headless_retry_secs; a successful retry forces a full
        # refresh and resumes normal rendering.
        self._headless = False
        self._headless_retry_secs = 30.0
        self._last_headless_retry = 0.0

        # LONG-3: screensaver state. Before the long-idle deep-sleep tier we paint
        # a mostly-white "paused" frame so a static high-contrast page doesn't sit
        # on the panel for hours. Tracked so it's painted exactly once per idle.
        self._screensaver_shown = False

        # Wakeup event — set by _on_any_key() to interrupt the loop's idle sleep
        self._wakeup = threading.Event()

        # Perf metrics
        get_perf().enabled = self._config.enable_perf_metrics
        self._last_perf_log: float = time.monotonic()

        # Watchdog socket (reused for session lifetime)
        self._watchdog_sock: socket.socket | None = None
        self._watchdog_addr: str = ""
        notify_socket = os.environ.get("NOTIFY_SOCKET", "")
        if notify_socket:
            addr = notify_socket
            if addr.startswith("@"):
                addr = "\0" + addr[1:]
            try:
                self._watchdog_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                self._watchdog_addr = addr
            except Exception:
                pass

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

        # Aggressive panel idle-sleep: deep-sleep the panel after this many
        # seconds of no keystroke (bounds the powered-and-idle window). This is
        # the effective Tier-1 trigger; falls back to display_off_minutes if the
        # aggressive trigger is disabled (0).
        idle_sleep_secs = self._config.display_idle_sleep_seconds
        if idle_sleep_secs > 0:
            display_off_secs = idle_sleep_secs

        # LONG-3: paint a white "paused" screensaver frame this many seconds into
        # idle, before the panel deep-sleeps, so a static page doesn't burn in.
        # Clamped to fire no later than the display-sleep trigger (0 = disabled).
        screensaver_secs = self._config.display_screensaver_seconds

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

            # FAULT-7: if the panel died at runtime, periodically try to bring it
            # back. Input drain + autosave above already ran, so words are safe
            # regardless of the panel. A successful retry resumes normal rendering
            # with a forced full refresh.
            if self._headless:
                self._maybe_retry_panel()

            # Sleep tier checks
            idle_secs = time.monotonic() - self._last_keypress

            # LONG-3: screensaver — blank to white just before the panel sleeps.
            if (
                screensaver_secs > 0
                and not self._display_sleeping
                and not self._headless
                and not self._screensaver_shown
                and idle_secs > min(screensaver_secs, display_off_secs)
            ):
                self._show_screensaver()

            # Tier 1: display sleep
            if (
                display_off_secs > 0
                and not self._display_sleeping
                and idle_secs > display_off_secs
            ):
                self._display_sleeping = True
                try:
                    self._driver.sleep()
                except Exception as e:
                    logger.warning("Display sleep failed: %s", e)
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
            if changed and not self._display_sleeping and not self._headless:
                if self._needs_display_wake:
                    try:
                        self._driver.wake()
                    except Exception as e:
                        logger.warning("Display wake failed: %s", e)
                    self._needs_display_wake = False
                    logger.info("Display woken from sleep")
                self._render_and_refresh()

            # Perf summary every 30s
            perf = get_perf()
            if perf.enabled and time.monotonic() - self._last_perf_log >= 30.0:
                perf.log_summary()
                self._last_perf_log = time.monotonic()

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
            from writerdeck.display.fonts import list_available_fonts
            from writerdeck.modes.font_picker import FontPickerOverlay
            self._overlay = FontPickerOverlay(list_available_fonts())
            self._refresh.request_full()
            return True
        if action == KeyAction.OUTLINE:
            from writerdeck.modes.outline_overlay import OutlineOverlay
            self._overlay = OutlineOverlay(self._doc._lines)
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
                # Preserve in-mode scroll state and cleanly exit the outgoing
                # mode before rebuilding, then re-enter the same mode index.
                # Also clear the wrap cache so old-font entries don't linger.
                scroll_offset = getattr(self._mode, "_scroll_offset", 0)
                self._mode.on_exit()
                self._config._data["font_family"] = result["font"]
                from writerdeck.utils.text_wrapper import clear_wrap_cache
                clear_wrap_cache()
                self._modes = self._build_modes()
                self._mode = self._modes[self._mode_idx % len(self._modes)]
                self._mode.on_enter()
                # on_enter() resets scroll to 0; restore the prior offset.
                if hasattr(self._mode, "_scroll_offset"):
                    self._mode._scroll_offset = scroll_offset
            elif "jump_to_line" in result:
                self._doc.cursor_line = result["jump_to_line"]
                self._doc.cursor_col = 0
                self._doc.selection = None
                self._mode._page_manual = False
            elif "find" in result:
                query = result["find"]
                replace = result.get("replace")
                if replace is not None:
                    # Locate the match first (wrap-around handled by find_next),
                    # move the cursor there, replace, then advance past the
                    # inserted text. replace_at only edits (and touches the undo
                    # stack) when the located text actually matches.
                    pos = self._doc.find_next(
                        query, self._doc.cursor_line, self._doc.cursor_col,
                    )
                    if pos is not None and self._doc.replace_at(
                        pos[0], pos[1], query, replace
                    ):
                        self._doc.cursor_line = pos[0]
                        self._doc.cursor_col = pos[1] + len(replace)
                        self._status.show("Replaced")
                    else:
                        self._status.show("Not found")
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
        perf = get_perf()

        with perf.time("total_frame"):
            with perf.time("render_frame"):
                frame = self._mode.render(self._doc, self._session)
            perf.record_gauge("doc_lines", len(self._doc._lines))

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
            if self._config.enable_battery_monitor and self._power.available and frame.stats is not None:
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

            # PERF-1: decouple the volatile stats cadence from per-keystroke input.
            # On the partial path, freeze the stats to the snapshot captured on the
            # last full refresh so the Words/timer/sidebar bytes are unchanged and
            # don't drag their rows into the dirty diff. Full refreshes paint (and
            # snapshot) the live values.
            if will_full:
                if frame.stats is not None:
                    self._stats_snapshot = dict(frame.stats)
            elif frame.stats is not None:
                frame.stats = (
                    dict(self._stats_snapshot) if self._stats_snapshot is not None else None
                )

            # FAULT-6/FAULT-7: the display op is bounded-retry wrapped in the driver.
            # If it still fails it raises DisplayError — catch it here, degrade to a
            # headless state (input + autosave keep running, panel retried on an
            # interval) and skip this frame rather than let the exception crash the
            # app and lose the session.
            try:
                if will_full:
                    deep_clean_threshold = self._config.idle_deep_clean_seconds
                    is_deep_clean = (
                        deep_clean_threshold > 0 and idle_secs >= deep_clean_threshold
                    )

                    if is_deep_clean:
                        # User has been away long enough — do a GC16 clean to wipe
                        # any accumulated ghosting. Uses init() waveform, not init_fast().
                        with perf.time("render_image"):
                            image = render(frame, self._config.font_family, self._config.font_size)
                        with perf.time("driver_display"):
                            self._driver.display_clean(image)
                    else:
                        with perf.time("render_image"):
                            image = render(frame, self._config.font_family, self._config.font_size)
                        with perf.time("driver_display"):
                            self._driver.display_full(image)
                else:
                    with perf.time("render_image"):
                        image = render(frame, self._config.font_family, self._config.font_size)
                    with perf.time("driver_display"):
                        self._driver.display_partial(image)
            except DisplayError:
                self._enter_headless()
                return

            self._refresh.record_refresh(was_full=will_full)

    # -- LONG-3 screensaver / FAULT-7 headless ----------------------------

    def _show_screensaver(self) -> None:
        """Paint a mostly-white 'paused' frame before long-idle deep sleep (LONG-3).

        A full refresh so the previous high-contrast page is fully cleared to
        white (retention mitigation). On the next keystroke the app wakes and
        forces a full refresh, restoring the page. Any display failure degrades
        to headless rather than crashing.
        """
        from writerdeck.display.splash import render_paused
        self._screensaver_shown = True
        try:
            self._driver.display_full(render_paused())
            logger.info("Screensaver shown (blanked to white before deep sleep)")
        except DisplayError:
            self._enter_headless()
        except Exception as e:
            logger.warning("Screensaver render failed: %s", e)

    def _enter_headless(self) -> None:
        """Switch to a headless/degraded mode after repeated panel failure (FAULT-7).

        The main loop keeps draining input, autosaving and persisting the session
        — only rendering is suspended. The panel is retried on an interval by
        _maybe_retry_panel(). Idempotent.
        """
        if self._headless:
            return
        self._headless = True
        self._last_headless_retry = time.monotonic()
        self._status.show("Display error — text is safe, retrying screen")
        logger.error(
            "Display failed repeatedly — entering headless mode; input and "
            "autosave continue, panel will be retried every %.0fs",
            self._headless_retry_secs,
        )

    def _maybe_retry_panel(self) -> None:
        """Periodically try to recover the panel while headless (FAULT-7).

        On success, resume normal rendering with a forced full refresh so the
        current document is redrawn from scratch.
        """
        now = time.monotonic()
        if now - self._last_headless_retry < self._headless_retry_secs:
            return
        self._last_headless_retry = now
        logger.info("Headless: retrying display panel")
        try:
            # Re-initialise the panel from scratch (also restores any state the
            # driver dropped on the fault). init() raises on hardware failure.
            self._driver.init()
        except Exception as e:
            logger.warning("Panel retry failed, staying headless: %s", e)
            return
        # Recovered — resume rendering with a full refresh.
        self._headless = False
        self._refresh.request_full()
        self._status.show("Display recovered")
        logger.info("Panel recovered — resuming rendering with a full refresh")
        try:
            self._render_and_refresh(force_full=True)
        except DisplayError:
            # Recovery frame failed again — fall straight back to headless.
            self._enter_headless()

    def _on_any_key(self) -> None:
        self._wakeup.set()
        self._last_keypress = time.monotonic()
        # PERF-4: reset the idle-full timer against the keypress so a brief
        # pause-then-type takes the partial path instead of a surprise full.
        self._refresh.note_keypress()
        # LONG-3: any key ends the idle period, so re-arm the screensaver for the
        # next idle stretch.
        self._screensaver_shown = False
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
        """Send WATCHDOG=1 to systemd using the persistent socket."""
        if self._watchdog_sock is None:
            return
        try:
            self._watchdog_sock.sendto(b"WATCHDOG=1", self._watchdog_addr)
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
        if self._watchdog_sock is not None:
            try:
                self._watchdog_sock.close()
            except Exception:
                pass
            self._watchdog_sock = None

    def _signal_handler(self, signum, frame) -> None:
        self._running = False  # just set flag — cleanup runs after the loop exits
