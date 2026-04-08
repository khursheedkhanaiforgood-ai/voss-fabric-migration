"""
Data models representing the configuration state of one Extreme 5320 switch.

Each SwitchModel tracks exactly what has been configured — starts in EXOS state,
transitions to VOSS/FabricEngine state as the student completes migration steps.

EXOS → VOSS key mental shift:
  EXOS: VLANs are just L2 domains. You manually trunk every VLAN on every uplink.
  VOSS: VLANs bind to I-SIDs (IEEE 802.1aq §12). I-SIDs flow automatically across
        the SPB fabric — zero config on NNI once ISIS adjacency is up.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SwitchOS(str, Enum):
    EXOS = "EXOS"
    VOSS = "VOSS"


@dataclass
class VlanConfig:
    vlan_id: int
    name: str
    isid: Optional[int] = None       # None until student runs `vlan i-sid`
    ip_address: Optional[str] = None  # e.g. "10.0.20.1"
    ip_prefix: int = 24
    dhcp_enabled: bool = False        # `ip dhcp-server enable` on interface vlan

    @property
    def has_isid(self) -> bool:
        return self.isid is not None

    @property
    def has_ip(self) -> bool:
        return self.ip_address is not None


@dataclass
class DhcpPool:
    vlan_id: int
    name: str
    network: str         # e.g. "10.0.20.0"
    mask: str            # e.g. "255.255.255.0"
    range_start: str
    range_end: str
    gateway: str
    dns: list[str] = field(default_factory=lambda: ["8.8.8.8", "8.8.4.4"])


@dataclass
class SwitchModel:
    """
    Complete configuration state of one Extreme 5320 running VOSS/FabricEngine.

    Starts in EXOS persona. Each validated CLI command updates the relevant field.
    The SimulationEngine reads these fields to synthesize `show` command output.
    """
    switch_id: str                    # "SW1" or "SW2"
    system_id: str                    # "0000.0000.0001"
    nick_name: str                    # "0.00.01"
    os: SwitchOS = SwitchOS.EXOS

    # ── ISIS / SPB Control Plane (IEEE 802.1aq + RFC 6329) ─────────────────
    isis_configured: bool = False     # `router isis` block entered
    isis_system_id: Optional[str] = None
    isis_manual_area: Optional[str] = None
    isis_enabled: bool = False        # `router isis enable`
    spbm_configured: bool = False     # `spbm 1` block entered
    spbm_ethertype: Optional[str] = None  # must be "0x8100"
    spbm_nick_name: Optional[str] = None

    # ── NNI Port (Port 17) ──────────────────────────────────────────────────
    nni_port: int = 17
    nni_isis_enabled: bool = False    # `isis enable` on interface gig 1/17
    nni_no_shutdown: bool = False

    # ── VLANs and I-SIDs (IEEE 802.1aq service model) ──────────────────────
    vlans: dict[int, VlanConfig] = field(default_factory=dict)

    # ── DHCP Server ─────────────────────────────────────────────────────────
    dhcp_server_enabled: bool = False
    dhcp_pools: dict[int, DhcpPool] = field(default_factory=dict)

    # ── Fabric Attach (IEEE 802.1Qcj) ───────────────────────────────────────
    fa_global_enabled: bool = False   # `fa enable` globally
    fa_ports: list[int] = field(default_factory=list)  # ports with auto-sense + fa enable

    # ── Internet Exit ────────────────────────────────────────────────────────
    internet_exit_vlan: Optional[int] = None   # VLAN 100
    internet_exit_ip: Optional[str] = None     # 192.168.1.2 (SW1) or .3 (SW2)
    default_route: Optional[str] = None        # "192.168.1.1"

    # ── IP Shortcuts (SW2 learns SW1 default route via Fabric) ──────────────
    ip_shortcut_enabled: bool = False

    # ── Save state ──────────────────────────────────────────────────────────
    config_saved: bool = False

    # ── Computed properties ─────────────────────────────────────────────────

    @property
    def isis_ready(self) -> bool:
        """True when ISIS is fully configured and enabled."""
        return (
            self.isis_configured
            and self.isis_system_id is not None
            and self.isis_manual_area is not None
            and self.isis_enabled
        )

    @property
    def spbm_ready(self) -> bool:
        """True when SPBM is configured with correct ethertype."""
        return (
            self.spbm_configured
            and self.spbm_ethertype == "0x8100"
            and self.spbm_nick_name is not None
        )

    @property
    def nni_ready(self) -> bool:
        """True when NNI port is configured for ISIS."""
        return self.nni_isis_enabled and self.nni_no_shutdown

    @property
    def vlans_with_isids(self) -> dict[int, VlanConfig]:
        return {vid: v for vid, v in self.vlans.items() if v.has_isid}

    @property
    def vlans_with_ip(self) -> dict[int, VlanConfig]:
        return {vid: v for vid, v in self.vlans.items() if v.has_ip}

    @property
    def fabric_ready(self) -> bool:
        """True when this switch is ready to form an ISIS adjacency."""
        return self.isis_ready and self.spbm_ready and self.nni_ready

    def summary_dict(self) -> dict:
        """Compact state summary for UI display."""
        return {
            "OS": self.os.value,
            "ISIS": "enabled" if self.isis_enabled else ("configured" if self.isis_configured else "not configured"),
            "SPBM ethertype": self.spbm_ethertype or "not set",
            "NNI (port 17)": "ISIS up" if self.nni_ready else "not configured",
            "VLANs": len(self.vlans),
            "I-SIDs": len(self.vlans_with_isids),
            "DHCP server": "enabled" if self.dhcp_server_enabled else "off",
            "FA global": "enabled" if self.fa_global_enabled else "off",
            "Default route": self.default_route or "none",
            "Config saved": "yes" if self.config_saved else "no",
        }
