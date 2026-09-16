"""ProtonVPN headless IP rotation manager.

Uses the community ProtonVPN CLI (Rafficer/linux-cli-community, AKA
`protonvpn-cli` on PyPI) which runs on OpenVPN and needs NO GUI and NO
NetworkManager — perfect for a headless VPS.

Install on a real VPS:
    sudo pip3 install protonvpn-cli
    sudo protonvpn init          # enter OpenVPN creds from
                                  # account.protonvpn.com/account
    # (optional) disable sudo prompt for cron:
    sudo visudo  →  add: youruser ALL=(root) NOPASSWD: /usr/local/bin/protonvpn

Commands used (all non-interactive flags):
    protonvpn c -r                 # connect to a RANDOM server
    protonvpn c --cc {country}      # fastest server in a COUNTRY
    protonvpn d                     # disconnect
    protonvpn s                     # status (non-root, prints IP)

Rotation strategy:
    - Cycle through a configured list of countries, picking a random order
      each cycle so the same country isn't always first.
    - Rotate every N collection batches (configurable).
    - If VPN fails to connect, log a warning and continue on the bare IP
      (better degraded operation than a hard stop — but flag it loudly).

Note: In a container/sandbox without kernel tun access, VPN can't actually
establish a tunnel.  `available()` returns False in that case so the
scraper runs without rotation but logs the limitation.  On a real VPS this
works as designed.
"""

from __future__ import annotations

import logging
import random
import shutil
import subprocess
import time
from typing import Optional

from ..config import VPNConfig

log = logging.getLogger(__name__)


class ProtonVPNManager:
    """Wraps the protonvpn CLI for headless IP rotation."""

    def __init__(self, cfg: VPNConfig):
        self.cfg = cfg
        self._batch_count = 0
        self._connected = False

    # -- availability ---------------------------------------------------------

    def available(self) -> bool:
        """True if the protonvpn binary exists AND we're initialized."""
        if not self.cfg.enabled:
            return False
        binary = shutil.which(self.cfg.protonvpn_bin)
        if not binary:
            log.debug(
                "ProtonVPN binary '%s' not on PATH — "
                "install with: sudo pip3 install protonvpn-cli && sudo protonvpn init",
                self.cfg.protonvpn_bin,
            )
            return False
        if not self.cfg.init_done:
            log.debug("ProtonVPN not initialized — run: sudo protonvpn init")
            return False
        return True

    # -- rotation --------------------------------------------------------------

    def maybe_rotate(self) -> bool:
        """Rotate IP if we've done enough batches.  Returns True if rotated."""
        if not self.available():
            return False

        self._batch_count += 1
        if self._batch_count % self.cfg.rotate_every_batches != 0:
            return False
        return self.rotate()

    def rotate(self) -> bool:
        """Connect to a new server in a random country.  Returns True on success."""
        if not self.available():
            log.warning("VPN rotation requested but ProtonVPN not available — "
                        "running on bare IP. DO NOT run login-based backends "
                        "(twifork) without VPN on a known IP.")
            return False

        # Pick a random country from the configured pool.
        countries = list(self.cfg.countries)
        random.shuffle(countries)

        # First try a random country (fastest-in-country); fall back to fully random.
        for attempt, country in enumerate(countries):
            ok = self._connect(country=country)
            if ok:
                self._connected = True
                ip = self.current_ip()
                log.info("VPN rotated → country=%s  ip=%s", country, ip or "?")
                return True
            log.debug("VPN connect to %s failed (attempt %d)", country, attempt + 1)

        # Last resort: fully random server (no country preference).
        ok = self._connect(random_server=True)
        if ok:
            self._connected = True
            log.info("VPN rotated → random server  ip=%s", self.current_ip() or "?")
            return True

        log.error("VPN rotation failed across all %d countries — "
                  "continuing on last connection or bare IP", len(countries))
        return False

    # -- low-level CLI wrappers -----------------------------------------------

    def _connect(self, country: Optional[str] = None, random_server: bool = False) -> bool:
        """Run a non-interactive connect command.  Returns True if connected."""
        if random_server:
            args = ["sudo", self.cfg.protonvpn_bin, "c", "-r"]
        elif country:
            args = ["sudo", self.cfg.protonvpn_bin, "c", "--cc", country]
        else:
            args = ["sudo", self.cfg.protonvpn_bin, "c", "-f"]

        try:
            # 45s timeout — VPN handshakes can be slow on first connect.
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=45,
            )
        except subprocess.TimeoutExpired:
            log.warning("VPN connect timed out (%s)", country or "random")
            return False
        except FileNotFoundError:
            log.error("protonvpn binary not found — install it first")
            return False

        if result.returncode != 0:
            stderr = result.stderr.strip()[:200]
            log.debug("VPN connect rc=%d stderr=%s", result.returncode, stderr)
            return False
        # Give the tunnel a moment to settle before scraping.
        time.sleep(3)
        return True

    def disconnect(self) -> None:
        if not self.available():
            return
        try:
            subprocess.run(
                ["sudo", self.cfg.protonvpn_bin, "d"],
                capture_output=True, text=True, timeout=20,
            )
            self._connected = False
        except Exception as exc:  # noqa: BLE001
            log.warning("VPN disconnect failed: %s", exc)

    def status(self) -> dict:
        """Return connection status + current IP."""
        if not self.available():
            return {"connected": False, "reason": "vpn_unavailable"}
        try:
            result = subprocess.run(
                ["sudo", self.cfg.protonvpn_bin, "s"],
                capture_output=True, text=True, timeout=10,
            )
        except Exception as exc:  # noqa: BLE001
            return {"connected": False, "error": str(exc)}
        out = result.stdout + result.stderr
        connected = "Connected" in out or "Status: Connected" in out
        return {
            "connected": connected,
            "raw": out.strip()[:500],
            "ip": self.current_ip(),
        }

    def current_ip(self) -> str:
        """Fetch the current public IP (via a public echo service)."""
        import httpx
        for svc in ("https://api.ipify.org", "https://ifconfig.me"):
            try:
                r = httpx.get(svc, timeout=8, follow_redirects=True)
                if r.status_code == 200:
                    return r.text.strip()
            except Exception:  # noqa: BLE001
                continue
        return ""

    @property
    def is_connected(self) -> bool:
        return self._connected
