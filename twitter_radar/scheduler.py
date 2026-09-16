"""Routine scheduler — runs collection cycles on a fixed interval.

Two modes:
  - `run_forever()`  — asyncio loop, sleeps interval_minutes between cycles.
  - `run_once()`     — single cycle; ideal for a cron job that calls this
                       script every N minutes (lets cron own the schedule).

VPN rotation happens before each cycle (or every N cycles, configurable).
The scheduler also handles graceful degradation: if VPN is unavailable,
it runs anyway but logs the limitation (twifork should be disabled in that
case via config to avoid login on a known IP).
"""

from __future__ import annotations

import logging
import time

from .collector import Collector
from .config import Config
from .vpn.proton import ProtonVPNManager

log = logging.getLogger(__name__)


class Scheduler:
    def __init__(
        self,
        cfg: Config,
        collector: Collector,
        vpn: ProtonVPNManager,
    ):
        self.cfg = cfg
        self.collector = collector
        self.vpn = vpn
        self.cycle_count = 0

    def run_once(self) -> dict:
        """Single collection cycle with VPN rotation.  Returns stats."""
        # Rotate IP before the cycle (if VPN is configured and available).
        if self.vpn.available():
            rotated = self.vpn.maybe_rotate()
            log.info(
                "VPN %s (IP: %s)",
                "rotated" if rotated else "unchanged",
                self.vpn.current_ip() or "n/a",
            )
        elif self.cfg.vpn.enabled:
            log.warning(
                "VPN enabled in config but unavailable — "
                "running WITHOUT IP rotation. Disable login-based backends "
                "(twifork) or set up ProtonVPN to avoid bans."
            )

        self.cycle_count += 1
        stats, findings = self.collector.run_cycle()
        stats["cycle"] = self.cycle_count
        return stats, findings

    def run_forever(self, max_cycles: int = 0) -> None:
        """Loop: run a cycle, sleep, repeat.  max_cycles=0 = infinite."""
        import signal
        running = [True]

        def _stop(signum, frame):
            running[0] = False
            log.info("Shutdown signal received — finishing current cycle.")

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        log.info(
            "Scheduler started — cycle every %d min. Press Ctrl+C to stop.",
            self.cfg.schedule.interval_minutes,
        )
        while running[0]:
            try:
                stats = self.run_once()
                log.info("Cycle %d done: %s", self.cycle_count, stats)
            except Exception as exc:  # noqa: BLE001
                log.error("Cycle %d failed: %s", self.cycle_count + 1, exc)

            if max_cycles and self.cycle_count >= max_cycles:
                break
            if not running[0]:
                break

            # Sleep in small increments so SIGINT is responsive.
            sleep_s = self.cfg.schedule.interval_minutes * 60
            slept = 0
            while slept < sleep_s and running[0]:
                time.sleep(min(5, sleep_s - slept))
                slept += 5

        # Cleanup
        if self.vpn.is_connected:
            self.vpn.disconnect()
        log.info("Scheduler stopped after %d cycles.", self.cycle_count)
