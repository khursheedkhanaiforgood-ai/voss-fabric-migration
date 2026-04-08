"""
OutputSynthesisService — generates realistic VOSS CLI `show` command output
based on the current SwitchModel state.

When a student types `show isis adjacency`, this service reads the LabState
and returns what a real VOSS switch would display at that point in the migration.
Critical teaching tool: incorrect config produces the correct "broken" output.
"""

from __future__ import annotations
from datetime import datetime

from ..models.switch_state import SwitchModel
from ..models.lab_state import LabState
from ..config import SERVICES


class OutputSynthesisService:

    def __init__(self, lab: LabState):
        self._lab = lab

    def render(self, command: str, switch_id: str) -> str:
        """Dispatch to the appropriate show renderer."""
        sw = self._lab.switch(switch_id)
        cmd = command.strip().lower()

        if cmd in ("show isis adjacency", "show isis adj"):
            return self._isis_adjacency(sw)
        if cmd in ("show isis", "show isis info"):
            return self._isis_info(sw)
        if cmd == "show isis interface":
            return self._isis_interface(sw)
        if cmd == "show spbm":
            return self._spbm(sw)
        if cmd in ("show i-sid", "show vlan i-sid"):
            return self._isid(sw)
        if cmd in ("show fa assignment", "show fa"):
            return self._fa_assignment(sw)
        if cmd == "show fa neighbor":
            return self._fa_neighbor(sw)
        if cmd in ("show ip route", "show ip route all"):
            return self._ip_route(sw)
        if cmd == "show vlan":
            return self._vlan(sw)
        if cmd == "show ip dhcp-server summary":
            return self._dhcp_summary(sw)
        if cmd == "show ip dhcp-server binding":
            return self._dhcp_binding(sw)
        if cmd == "show application iqagent status":
            return self._iqagent(sw)
        if cmd == "show version":
            return self._version(sw)

        return (
            f"% Unknown show command: `{command}`\n"
            "Supported: show isis [adjacency|interface], show spbm, show i-sid, "
            "show fa [assignment|neighbor], show ip route, show vlan, "
            "show ip dhcp-server [summary|binding], show application iqagent status, show version"
        )

    def supports(self, command: str) -> bool:
        return command.strip().lower().startswith("show ")

    # ── Individual show renderers ─────────────────────────────────────────────

    def _isis_adjacency(self, sw: SwitchModel) -> str:
        lab = self._lab
        if not sw.isis_enabled:
            return (
                f"\n{sw.switch_id} - show isis adjacency\n"
                "================================================================================\n"
                "IS-IS is not enabled.\n"
                "  Run: `router isis enable`\n"
            )
        if not sw.nni_ready:
            return (
                f"\n{sw.switch_id} - show isis adjacency\n"
                "================================================================================\n"
                "No ISIS interfaces configured.\n"
                "  Run: `interface gigabitEthernet 1/17` → `isis enable` + `no shutdown`\n"
            )
        adj_up = lab.isis_adjacency_up
        reason = lab.adjacency_failure_reason()
        peer_id = "0000.0000.0002" if sw.switch_id == "SW1" else "0000.0000.0001"
        peer_nn = "0.00.02" if sw.switch_id == "SW1" else "0.00.01"
        state = "UP" if adj_up else "DOWN"
        state_detail = "L1L2" if adj_up else "INIT"
        port = "1/17"
        lines = [
            f"\n{sw.switch_id} - show isis adjacency",
            "=" * 80,
            f"{'System ID':<20} {'Nick-Name':<12} {'State':<8} {'Interface':<12} {'Hold Time':<10}",
            "-" * 80,
            f"{peer_id:<20} {peer_nn:<12} {state:<8} Port {port:<8} {'27s' if adj_up else 'N/A':<10}",
            "",
        ]
        if not adj_up and reason:
            lines.append(f"  [FAULT] Adjacency DOWN — {reason}")
        lines.append("")
        return "\n".join(lines)

    def _isis_info(self, sw: SwitchModel) -> str:
        return (
            f"\n{sw.switch_id} - show isis\n"
            "=" * 60 + "\n"
            f"  IS-IS System ID   : {sw.isis_system_id or 'not configured'}\n"
            f"  Manual Area       : {sw.isis_manual_area or 'not configured'}\n"
            f"  Admin State       : {'enabled' if sw.isis_enabled else 'disabled'}\n"
            f"  SPBM ethertype    : {sw.spbm_ethertype or 'not configured'}\n"
            f"  SPBM nick-name    : {sw.spbm_nick_name or 'not configured'}\n"
        )

    def _isis_interface(self, sw: SwitchModel) -> str:
        lines = [
            f"\n{sw.switch_id} - show isis interface",
            "=" * 70,
            f"{'Port':<10} {'Admin':<10} {'Oper':<10} {'Type':<15} {'Metric':<8}",
            "-" * 70,
        ]
        if sw.nni_isis_enabled:
            oper = "Up" if sw.nni_no_shutdown else "Down"
            lines.append(f"{'1/17':<10} {'enabled':<10} {oper:<10} {'P2P':<15} {'10':<8}")
        else:
            lines.append("  No ISIS interfaces configured.")
        lines.append("")
        return "\n".join(lines)

    def _spbm(self, sw: SwitchModel) -> str:
        if not sw.spbm_configured:
            return (
                f"\n{sw.switch_id} - show spbm\n"
                "SPBM not configured. Run: `spbm 1` → `nick-name` → `ethertype 0x8100`\n"
            )
        mismatch = sw.spbm_ethertype != "0x8100"
        warning = "  [WARNING] ethertype != 0x8100 — adjacency will NOT form!" if mismatch else ""
        return (
            f"\n{sw.switch_id} - show spbm\n"
            "=" * 60 + "\n"
            f"  SPBM Instance     : 1\n"
            f"  Nick-Name         : {sw.spbm_nick_name or 'not set'}\n"
            f"  System ID         : {sw.system_id}\n"
            f"  Ethertype         : {sw.spbm_ethertype or 'not set'}\n"
            f"  Admin State       : {'enabled' if sw.isis_enabled else 'not enabled'}\n"
            f"{warning}\n"
        )

    def _isid(self, sw: SwitchModel) -> str:
        lines = [
            f"\n{sw.switch_id} - show i-sid",
            "=" * 70,
            f"{'I-SID':<10} {'VLAN':<8} {'Name':<12} {'Type':<8} {'State':<10}",
            "-" * 70,
        ]
        if not sw.vlans_with_isids:
            lines.append("  No I-SIDs configured. Run: `vlan i-sid <vlan> <isid>`")
        else:
            for vid, vcfg in sorted(sw.vlans_with_isids.items()):
                state = "active" if self._lab.isis_adjacency_up else "local"
                lines.append(f"{vcfg.isid:<10} {vid:<8} {vcfg.name:<12} {'ELAN':<8} {state:<10}")
        lines.append("")
        return "\n".join(lines)

    def _fa_assignment(self, sw: SwitchModel) -> str:
        lines = [
            f"\n{sw.switch_id} - show fa assignment",
            "=" * 70,
            f"{'VLAN':<8} {'I-SID':<10} {'Port':<8} {'State':<10} {'Type':<10}",
            "-" * 70,
        ]
        if not sw.fa_global_enabled:
            lines.append("  Fabric Attach not enabled. Run: `fa enable`")
            lines.append("")
            return "\n".join(lines)
        if sw.switch_id not in sw.fa_ports and 3 not in sw.fa_ports:
            lines.append("  No FA-enabled ports. Run: `interface gigabitEthernet 1/3` → `fa enable`")
            lines.append("")
            return "\n".join(lines)
        for vid, vcfg in sorted(sw.vlans_with_isids.items()):
            if vid == 10:
                continue  # MGMT VLAN not FA-assigned
            state = "ACTIVE" if self._lab.isis_adjacency_up else "PENDING"
            lines.append(f"{vid:<8} {vcfg.isid:<10} {'1/3':<8} {state:<10} {'DYNAMIC':<10}")
        if not sw.vlans_with_isids:
            lines.append("  No I-SIDs defined — FA assignments will stay PENDING.")
        lines.append("")
        return "\n".join(lines)

    def _fa_neighbor(self, sw: SwitchModel) -> str:
        if not sw.fa_global_enabled or 3 not in sw.fa_ports:
            return (
                f"\n{sw.switch_id} - show fa neighbor\n"
                "  No FA neighbors. Enable: `fa enable` + port `auto-sense enable` + `fa enable`\n"
            )
        return (
            f"\n{sw.switch_id} - show fa neighbor\n"
            "=" * 70 + "\n"
            f"  Port 1/3: AP3000 (Fabric Attach Client)\n"
            f"  LLDP Chassis ID : 00:1F:45:AB:CD:{('01' if sw.switch_id == 'SW1' else '02')}\n"
            f"  FA TLV          : Present — requesting VLANs 20,30 (or 50,60)\n\n"
        )

    def _ip_route(self, sw: SwitchModel) -> str:
        lines = [
            f"\n{sw.switch_id} - show ip route",
            "=" * 70,
            f"{'Dest':<20} {'Mask':<18} {'NextHop':<18} {'Type':<8} {'Metric':<8}",
            "-" * 70,
        ]
        # Connected routes from VLAN IPs
        for vid, vcfg in sorted(sw.vlans_with_ip.items()):
            net = vcfg.ip_address.rsplit(".", 1)[0] + ".0"
            lines.append(f"{net:<20} {'255.255.255.0':<18} {'0.0.0.0':<18} {'C':<8} {'0':<8}")
        # Default route
        if sw.default_route:
            lines.append(f"{'0.0.0.0':<20} {'0.0.0.0':<18} {sw.default_route:<18} {'S':<8} {'1':<8}")
        elif sw.ip_shortcut_enabled and self._lab.isis_adjacency_up and sw.switch_id == "SW2":
            other = self._lab.sw1
            if other.default_route:
                lines.append(
                    f"{'0.0.0.0':<20} {'0.0.0.0':<18} {other.default_route:<18} "
                    f"{'ISIS':<8} {'1':<8}  (via ip-shortcut)"
                )
        if not sw.vlans_with_ip and not sw.default_route:
            lines.append("  No IP routes. Configure interface VLANs and default route.")
        lines.append("")
        return "\n".join(lines)

    def _vlan(self, sw: SwitchModel) -> str:
        lines = [
            f"\n{sw.switch_id} - show vlan",
            "=" * 70,
            f"{'VLAN':<8} {'Name':<14} {'I-SID':<10} {'Ports':<12}",
            "-" * 70,
        ]
        if not sw.vlans:
            lines.append("  No VLANs created. Run: `vlan create <id> name <name> type port-mstprstp 0`")
        for vid, vcfg in sorted(sw.vlans.items()):
            isid_str = str(vcfg.isid) if vcfg.isid else "none"
            lines.append(f"{vid:<8} {vcfg.name:<14} {isid_str:<10}")
        lines.append("")
        return "\n".join(lines)

    def _dhcp_summary(self, sw: SwitchModel) -> str:
        if not sw.dhcp_server_enabled:
            return (
                f"\n{sw.switch_id} - show ip dhcp-server summary\n"
                "  DHCP server not enabled. Run: `ip dhcp-server enable`\n"
            )
        lines = [
            f"\n{sw.switch_id} - show ip dhcp-server summary",
            "=" * 60,
            f"  DHCP Server State : Enabled",
            f"  Pools configured  : {len(sw.dhcp_pools)}",
            "",
        ]
        for vid, pool in sorted(sw.dhcp_pools.items()):
            lines.append(f"  Pool '{pool.name}': {pool.network}/{pool.mask}")
            lines.append(f"    Range: {pool.range_start} - {pool.range_end}")
        lines.append("")
        return "\n".join(lines)

    def _dhcp_binding(self, sw: SwitchModel) -> str:
        if not sw.dhcp_server_enabled:
            return f"\n{sw.switch_id} - show ip dhcp-server binding\n  DHCP server not enabled.\n"
        if not self._lab.e2e_connectivity:
            return (
                f"\n{sw.switch_id} - show ip dhcp-server binding\n"
                "  No bindings yet — fabric or DHCP not fully configured.\n"
            )
        # Simulate one binding per SSID VLAN
        lines = [f"\n{sw.switch_id} - show ip dhcp-server binding", "=" * 60]
        sims = [(20, "10.0.20.100", "iPhone-Alpha"), (30, "10.0.30.100", "iPhone-Bravo"),
                (50, "10.0.50.100", "iPhone-Delta"), (60, "10.0.60.100", "iPhone-Gamma")]
        for vid, ip, host in sims:
            lines.append(f"  IP: {ip:<16} VLAN: {vid:<6} Hostname: {host}")
        lines.append("")
        return "\n".join(lines)

    def _iqagent(self, sw: SwitchModel) -> str:
        connected = self._lab.sw1.isis_enabled or sw.isis_enabled  # basic proxy
        state = "Connected" if connected else "Connecting"
        return (
            f"\n{sw.switch_id} - show application iqagent status\n"
            "=" * 60 + "\n"
            f"  Connection : {state}\n"
            f"  Server     : hac.extremecloudiq.com\n"
            f"  Uptime     : {'12m 34s' if connected else 'N/A'}\n\n"
        )

    def _version(self, sw: SwitchModel) -> str:
        os_str = "FabricEngine 8.9" if sw.os.value == "VOSS" else "SwitchEngine 33.1"
        return (
            f"\n{sw.switch_id} - show version\n"
            "=" * 60 + "\n"
            f"  Model    : Extreme 5320-16P-2MXT-2X\n"
            f"  OS       : {os_str}\n"
            f"  System ID: {sw.system_id}\n\n"
        )
