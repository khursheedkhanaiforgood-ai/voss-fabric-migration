"""
LabState — holds the complete state of both switches and computes
cross-switch derived properties (ISIS adjacency, fabric health).

This is the single source of truth that all services read from and write to.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime

from .switch_state import SwitchModel, SwitchOS
from ..config import SWITCHES, SPBM


def _make_sw1() -> SwitchModel:
    cfg = SWITCHES["SW1"]
    return SwitchModel(
        switch_id="SW1",
        system_id=cfg["system_id"],
        nick_name=cfg["nick_name"],
        os=SwitchOS.EXOS,
    )


def _make_sw2() -> SwitchModel:
    cfg = SWITCHES["SW2"]
    return SwitchModel(
        switch_id="SW2",
        system_id=cfg["system_id"],
        nick_name=cfg["nick_name"],
        os=SwitchOS.EXOS,
    )


@dataclass
class LabState:
    """
    Runtime state of the two-switch lab.

    Both switches start in EXOS persona. As the student types VOSS commands,
    the relevant SwitchModel fields are updated by CommandValidatorService.
    """
    sw1: SwitchModel = field(default_factory=_make_sw1)
    sw2: SwitchModel = field(default_factory=_make_sw2)
    started_at: datetime = field(default_factory=datetime.now)
    active_switch: str = "SW1"   # which switch the student is currently configuring

    def switch(self, switch_id: str) -> SwitchModel:
        """Return the SwitchModel for a given switch_id."""
        if switch_id.upper() == "SW1":
            return self.sw1
        elif switch_id.upper() == "SW2":
            return self.sw2
        raise ValueError(f"Unknown switch_id: {switch_id}")

    def active(self) -> SwitchModel:
        return self.switch(self.active_switch)

    # ── Cross-switch derived properties ──────────────────────────────────────

    @property
    def isis_adjacency_up(self) -> bool:
        """
        True only when BOTH switches have:
          - ISIS enabled (router isis enable)
          - Matching manual-area (00.0001)
          - Matching SPBM ethertype (0x8100) — most common failure cause
          - NNI port (17) with isis enable + no shutdown

        IEEE 802.1aq / RFC 6329: IS-IS hellos are sent as multicast on the NNI.
        Ethertype mismatch causes silent L2 drop — hellos never reach the peer.
        """
        s1, s2 = self.sw1, self.sw2
        return (
            s1.fabric_ready
            and s2.fabric_ready
            and s1.isis_manual_area == s2.isis_manual_area
            and s1.spbm_ethertype == s2.spbm_ethertype == SPBM["ethertype"]
            and s1.isis_system_id != s2.isis_system_id  # must be unique
        )

    @property
    def fabric_services_visible(self) -> bool:
        """True when ISIS adjacency is up AND both switches have matching I-SIDs."""
        if not self.isis_adjacency_up:
            return False
        sw1_isids = set(v.isid for v in self.sw1.vlans.values() if v.isid)
        sw2_isids = set(v.isid for v in self.sw2.vlans.values() if v.isid)
        return sw1_isids == sw2_isids

    @property
    def e2e_connectivity(self) -> bool:
        """True when fabric is up, DHCP is serving, and SW1 has a default route."""
        return (
            self.fabric_services_visible
            and self.sw1.dhcp_server_enabled
            and self.sw1.default_route is not None
        )

    def adjacency_failure_reason(self) -> str | None:
        """
        Returns a human-readable explanation of why ISIS adjacency is down.
        Mirrors the troubleshooting decision tree from the VOSS agent.
        """
        s1, s2 = self.sw1, self.sw2
        if not s1.isis_enabled:
            return "SW1: `router isis enable` not run yet"
        if not s2.isis_enabled:
            return "SW2: `router isis enable` not run yet"
        if s1.spbm_ethertype != s2.spbm_ethertype:
            return (
                f"SPBM ethertype mismatch: SW1={s1.spbm_ethertype or 'not set'} "
                f"SW2={s2.spbm_ethertype or 'not set'} — "
                "IS-IS hellos silently dropped (IEEE 802.1aq §12)"
            )
        if s1.isis_manual_area != s2.isis_manual_area:
            return (
                f"IS-IS area mismatch: SW1={s1.isis_manual_area or 'not set'} "
                f"SW2={s2.isis_manual_area or 'not set'}"
            )
        if s1.isis_system_id == s2.isis_system_id:
            return f"System-ID conflict: both switches are {s1.isis_system_id}"
        if not s1.nni_ready:
            return "SW1: NNI port 17 not configured (missing `isis enable` or `no shutdown`)"
        if not s2.nni_ready:
            return "SW2: NNI port 17 not configured (missing `isis enable` or `no shutdown`)"
        return None

    def health_summary(self) -> dict:
        return {
            "ISIS adjacency": "UP" if self.isis_adjacency_up else "DOWN",
            "Fabric services visible": "yes" if self.fabric_services_visible else "no",
            "E2E connectivity": "yes" if self.e2e_connectivity else "no",
            "Adjacency failure reason": self.adjacency_failure_reason() or "n/a",
        }
