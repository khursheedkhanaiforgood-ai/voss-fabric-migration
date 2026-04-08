"""
18-step migration sequence: EXOS/SwitchEngine → VOSS/FabricEngine.

Each MigrationStep includes:
  - What to do (description)
  - Which switch(es) it applies to
  - Whether it's destructive (requires confirmation)
  - Prerequisite learning from the EXOS lab (linked list back to source project)
  - The governing standard (IEEE/RFC)

Learning path assumption: student has already completed the EXOS lab at
  https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/
and understands VLANs, DHCP, static routing, and AP3000 adoption in XIQ.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto


class Phase(str, Enum):
    """Three phases matching the project's migration plan."""
    PHASE_1_OS = "Phase 1 — OS Conversion"
    PHASE_2_FABRIC = "Phase 2 — SPB Fabric + Services"
    PHASE_3_VERIFY = "Phase 3 — DHCP, Routing, AP Verification"


@dataclass
class MigrationStep:
    number: int
    key: str                          # short identifier
    name: str
    phase: Phase
    applies_to: list[str]             # ["SW1", "SW2"] or ["SW1"] etc.
    description: str
    exos_parallel: str                # what the student did in EXOS — the learning link
    standard: str                     # governing IEEE/RFC
    is_destructive: bool = False
    is_narrative: bool = False        # no CLI commands — confirm to advance
    expected_commands: dict[str, list[str]] = field(default_factory=dict)
    verification_command: str = ""


# ─── The 18 Steps ─────────────────────────────────────────────────────────────

MIGRATION_STEPS: list[MigrationStep] = [

    MigrationStep(
        number=1,
        key="backup_exos",
        name="Backup EXOS Configuration",
        phase=Phase.PHASE_1_OS,
        applies_to=["SW1", "SW2"],
        description=(
            "Save the running EXOS config before the OS change wipes everything. "
            "USB export + XIQ backup. This config is your rollback path."
        ),
        exos_parallel=(
            "In the EXOS lab you used `save configuration` and XIQ Backups. "
            "Here: `save configuration as-script switch1_backup.xsf` + copy to USB."
        ),
        standard="N/A — operational procedure",
        is_destructive=False,
        is_narrative=True,
        expected_commands={
            "SW1": ["save configuration as-script switch1_backup.xsf"],
            "SW2": ["save configuration as-script switch2_backup.xsf"],
        },
        verification_command="show file /usr/local/ext/switch1_backup.xsf",
    ),

    MigrationStep(
        number=2,
        key="change_os",
        name="Change OS to VOSS/FabricEngine",
        phase=Phase.PHASE_1_OS,
        applies_to=["SW1", "SW2"],
        description=(
            "Boot menu (spacebar) → 'Change OS to VOSS', or XIQ: Actions → Change OS. "
            "DESTRUCTIVE — wipes all config, logs, events. Switch reboots."
        ),
        exos_parallel=(
            "In the EXOS lab you used ZTP+ to adopt the switch. After OS change, "
            "ZTP+ runs again from scratch under the VOSS/FabricEngine persona."
        ),
        standard="Extreme 5320 Universal Hardware — dual-persona capability",
        is_destructive=True,
        is_narrative=True,
        expected_commands={},
        verification_command="show version",
    ),

    MigrationStep(
        number=3,
        key="ztp_readopt",
        name="ZTP+ Re-Adoption in XIQ",
        phase=Phase.PHASE_1_OS,
        applies_to=["SW1", "SW2"],
        description=(
            "After reboot in VOSS persona, the switch ZTPs into XIQ. "
            "Assign to your XIQ org, apply FabricEngine device template."
        ),
        exos_parallel=(
            "Identical process to the EXOS lab onboarding at "
            "https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/ — "
            "same XIQ org, same DHCP discovery via VLAN 1."
        ),
        standard="XIQ ZTP+ — same flow regardless of EXOS or VOSS persona",
        is_narrative=True,
        expected_commands={},
        verification_command="show application iqagent status",
    ),

    MigrationStep(
        number=4,
        key="config_isis",
        name="Configure Router ISIS",
        phase=Phase.PHASE_2_FABRIC,
        applies_to=["SW1", "SW2"],
        description=(
            "Enter the IS-IS routing process and set the system-ID and manual-area. "
            "These must be UNIQUE per switch and IDENTICAL for manual-area. "
            "RFC 6329: system-ID maps to IS-IS NET address in SPB deployments."
        ),
        exos_parallel=(
            "EXOS has no ISIS — this is entirely new. In EXOS you used static routes "
            "(`configure iproute add default`). VOSS uses IS-IS to distribute routes "
            "across the fabric automatically via ip-shortcut."
        ),
        standard="RFC 6329 — IS-IS Extensions for IEEE 802.1aq",
        expected_commands={
            "SW1": ["router isis", "system-id 0000.0000.0001", "manual-area 00.0001", "exit"],
            "SW2": ["router isis", "system-id 0000.0000.0002", "manual-area 00.0001", "exit"],
        },
        verification_command="show isis",
    ),

    MigrationStep(
        number=5,
        key="config_spbm",
        name="Configure SPBM Instance",
        phase=Phase.PHASE_2_FABRIC,
        applies_to=["SW1", "SW2"],
        description=(
            "Configure SPBM instance 1: ethertype 0x8100 and nick-name. "
            "Ethertype MUST match on both switches — mismatch causes silent L2 drop. "
            "Nick-name is the human-readable SPBM node identifier."
        ),
        exos_parallel=(
            "No EXOS equivalent. SPB (IEEE 802.1aq) replaces STP — "
            "instead of blocking ports to prevent loops, IS-IS computes loop-free "
            "shortest-path trees. All ports active simultaneously."
        ),
        standard="IEEE 802.1aq — Shortest Path Bridging (SPBM instance configuration)",
        expected_commands={
            "SW1": ["spbm 1", "nick-name 0.00.01", "ethertype 0x8100", "exit"],
            "SW2": ["spbm 1", "nick-name 0.00.02", "ethertype 0x8100", "exit"],
        },
        verification_command="show spbm",
    ),

    MigrationStep(
        number=6,
        key="enable_isis",
        name="Enable Router ISIS",
        phase=Phase.PHASE_2_FABRIC,
        applies_to=["SW1", "SW2"],
        description=(
            "Activate the IS-IS process globally. ISIS will not send hellos until enabled. "
            "This is a separate step from configuration — by design, so you can "
            "configure everything before bringing up the control plane."
        ),
        exos_parallel=(
            "EXOS: no ISIS. Closest analog: `enable ospf` after configuring OSPF areas. "
            "Same separation of configure-then-enable pattern."
        ),
        standard="RFC 6329 §4 — IS-IS control plane activation for SPB",
        expected_commands={
            "SW1": ["router isis enable"],
            "SW2": ["router isis enable"],
        },
        verification_command="show isis",
    ),

    MigrationStep(
        number=7,
        key="config_nni",
        name="Configure NNI Port (Port 17)",
        phase=Phase.PHASE_2_FABRIC,
        applies_to=["SW1", "SW2"],
        description=(
            "Enable ISIS on the NNI port. This is where IS-IS hellos are sent. "
            "Port 17 is the Multi-Gig RJ45 — preferred over SFP+ for fabric backbone. "
            "MTU must be ≥1522 to accommodate MAC-in-MAC overhead (IEEE 802.1ah)."
        ),
        exos_parallel=(
            "In EXOS you manually trunked every VLAN on the inter-switch uplink. "
            "In VOSS: zero VLAN config on NNI — I-SIDs flow automatically once ISIS "
            "adjacency is up. This is the 'zero-config NNI' advantage of SPB."
        ),
        standard="IEEE 802.1ah — PBB MAC-in-MAC requires NNI MTU ≥1522",
        expected_commands={
            "SW1": ["interface gigabitEthernet 1/17", "isis enable", "isis network point-to-point", "no shutdown", "exit"],
            "SW2": ["interface gigabitEthernet 1/17", "isis enable", "isis network point-to-point", "no shutdown", "exit"],
        },
        verification_command="show isis interface",
    ),

    MigrationStep(
        number=8,
        key="create_vlans",
        name="Create VLANs 10/20/30/50/60",
        phase=Phase.PHASE_2_FABRIC,
        applies_to=["SW1", "SW2"],
        description=(
            "Create the five service VLANs. These must exist on BOTH switches "
            "before I-SID binding — the fabric service is only active when the "
            "corresponding I-SID is defined on each BEB (Backbone Edge Bridge)."
        ),
        exos_parallel=(
            "In EXOS: `create vlan Corp tag 20`. In VOSS: `vlan create 20 name Alpha "
            "type port-mstprstp 0`. Same concept — the I-SID binding in the next "
            "step is what makes this a Fabric service instead of a local VLAN."
        ),
        standard="IEEE 802.1aq §12 — BEB VLAN-to-I-SID binding",
        expected_commands={
            "SW1": [
                "vlan create 10 name MGMT type port-mstprstp 0",
                "vlan create 20 name Alpha type port-mstprstp 0",
                "vlan create 30 name Bravo type port-mstprstp 0",
                "vlan create 50 name Delta type port-mstprstp 0",
                "vlan create 60 name Gamma type port-mstprstp 0",
            ],
            "SW2": [
                "vlan create 10 name MGMT type port-mstprstp 0",
                "vlan create 20 name Alpha type port-mstprstp 0",
                "vlan create 30 name Bravo type port-mstprstp 0",
                "vlan create 50 name Delta type port-mstprstp 0",
                "vlan create 60 name Gamma type port-mstprstp 0",
            ],
        },
        verification_command="show vlan",
    ),

    MigrationStep(
        number=9,
        key="assign_isids",
        name="Assign I-SIDs to VLANs",
        phase=Phase.PHASE_2_FABRIC,
        applies_to=["SW1", "SW2"],
        description=(
            "Bind each VLAN to its I-SID (I-SID = VLAN ID + 100,000 convention). "
            "This is the core of SPB service definition. IEEE 802.1aq calls this "
            "an E-LAN service — once both BEBs have the same VLAN→I-SID binding, "
            "traffic for that service is automatically forwarded across the fabric."
        ),
        exos_parallel=(
            "No EXOS equivalent. In EXOS you trunked VLANs manually across uplinks. "
            "I-SIDs eliminate that entirely — define once, fabric handles distribution. "
            "FA (IEEE 802.1Qcj) also uses I-SIDs to auto-assign VLANs to AP ports."
        ),
        standard="IEEE 802.1aq §12.5 — I-SID: 24-bit service instance identifier for E-LAN/E-Line",
        expected_commands={
            "SW1": [
                "vlan i-sid 10 100010",
                "vlan i-sid 20 100020",
                "vlan i-sid 30 100030",
                "vlan i-sid 50 100050",
                "vlan i-sid 60 100060",
            ],
            "SW2": [
                "vlan i-sid 10 100010",
                "vlan i-sid 20 100020",
                "vlan i-sid 30 100030",
                "vlan i-sid 50 100050",
                "vlan i-sid 60 100060",
            ],
        },
        verification_command="show i-sid",
    ),

    MigrationStep(
        number=10,
        key="config_iface_vlans",
        name="Configure Interface VLANs (Anycast Gateways)",
        phase=Phase.PHASE_2_FABRIC,
        applies_to=["SW1", "SW2"],
        description=(
            "Assign the same IP address (e.g. 10.0.20.1/24) to VLAN 20 on BOTH switches. "
            "This is the Anycast Gateway — clients always use 10.0.20.1 regardless "
            "of which switch they are connected to. Note: `ip forwarding` is implicit "
            "in VOSS — assigning an IP address activates L3 routing automatically."
        ),
        exos_parallel=(
            "EXOS: `configure vlan Corp ipaddress 10.0.20.1/24` + "
            "`enable ipforwarding vlan Corp`. "
            "VOSS: `interface vlan 20` → `ip address 10.0.20.1/24` — NO `enable ipforwarding` needed. "
            "Also: SVIs are 10.0.x.1 in VOSS (not 10.10.0.x as in your EXOS lab)."
        ),
        standard="IEEE 802.1aq — BEB L3 gateway; ip forwarding implicit per VOSS design",
        expected_commands={
            "SW1": [
                "interface vlan 10", "ip address 10.0.10.1/24", "exit",
                "interface vlan 20", "ip address 10.0.20.1/24", "ip dhcp-server enable", "exit",
                "interface vlan 30", "ip address 10.0.30.1/24", "ip dhcp-server enable", "exit",
                "interface vlan 50", "ip address 10.0.50.1/24", "ip dhcp-server enable", "exit",
                "interface vlan 60", "ip address 10.0.60.1/24", "ip dhcp-server enable", "exit",
            ],
            "SW2": [
                "interface vlan 10", "ip address 10.0.10.1/24", "exit",
                "interface vlan 20", "ip address 10.0.20.1/24", "exit",
                "interface vlan 30", "ip address 10.0.30.1/24", "exit",
                "interface vlan 50", "ip address 10.0.50.1/24", "exit",
                "interface vlan 60", "ip address 10.0.60.1/24", "exit",
            ],
        },
        verification_command="show ip interface",
    ),

    MigrationStep(
        number=11,
        key="config_dhcp",
        name="Configure DHCP Server (SW1 only)",
        phase=Phase.PHASE_2_FABRIC,
        applies_to=["SW1"],
        description=(
            "SW1 is the authoritative DHCP server for all VLANs. SW2 clients "
            "reach SW1 DHCP via the SPB fabric — no DHCP relay config needed "
            "because Anycast Gateways handle L3 forwarding transparently."
        ),
        exos_parallel=(
            "EXOS: `configure vlan Corp dhcp-address-range 10.0.20.100 10.0.20.200` "
            "+ `enable dhcp ports 3 vlan Corp`. "
            "VOSS: `ip dhcp-server enable` globally + pool per VLAN + "
            "`ip dhcp-server enable` under `interface vlan`. Two separate enables."
        ),
        standard="RFC 2131 — DHCP; VOSS implementation via ip dhcp-server",
        expected_commands={
            "SW1": [
                "ip dhcp-server enable",
                "ip dhcp-server pool Alpha",
                "network-address 10.0.20.0 255.255.255.0",
                "range 10.0.20.100 10.0.20.200",
                "default-router 10.0.20.1",
                "dns-server 8.8.8.8 8.8.4.4",
                "exit",
                "ip dhcp-server pool Bravo",
                "network-address 10.0.30.0 255.255.255.0",
                "range 10.0.30.100 10.0.30.200",
                "default-router 10.0.30.1",
                "dns-server 8.8.8.8 8.8.4.4",
                "exit",
                "ip dhcp-server pool Delta",
                "network-address 10.0.50.0 255.255.255.0",
                "range 10.0.50.100 10.0.50.200",
                "default-router 10.0.50.1",
                "dns-server 8.8.8.8 8.8.4.4",
                "exit",
                "ip dhcp-server pool Gamma",
                "network-address 10.0.60.0 255.255.255.0",
                "range 10.0.60.100 10.0.60.200",
                "default-router 10.0.60.1",
                "dns-server 8.8.8.8 8.8.4.4",
                "exit",
            ],
        },
        verification_command="show ip dhcp-server summary",
    ),

    MigrationStep(
        number=12,
        key="config_fa",
        name="Configure Fabric Attach (Port 3 — AP3000)",
        phase=Phase.PHASE_2_FABRIC,
        applies_to=["SW1", "SW2"],
        description=(
            "Enable Fabric Attach globally and on Port 3 with auto-sense. "
            "The AP3000 uses LLDP-FA TLVs (IEEE 802.1Qcj) to request VLAN→I-SID bindings. "
            "auto-sense enables the port to accept FA requests dynamically — "
            "no manual VLAN trunking needed on the AP port."
        ),
        exos_parallel=(
            "EXOS: manually add VLANs to AP port — `configure vlan Corp add ports 3 tagged`. "
            "VOSS FA: zero config on AP port — the AP tells the switch which VLANs it needs "
            "via LLDP-FA TLVs. Same result, but AP-driven instead of admin-driven."
        ),
        standard="IEEE 802.1Qcj — Automatic Attachment to Provider Backbone Bridging Services (Fabric Attach)",
        expected_commands={
            "SW1": [
                "fa enable",
                "interface gigabitEthernet 1/3",
                "auto-sense enable",
                "fa enable",
                "no shutdown",
                "exit",
            ],
            "SW2": [
                "fa enable",
                "interface gigabitEthernet 1/3",
                "auto-sense enable",
                "fa enable",
                "no shutdown",
                "exit",
            ],
        },
        verification_command="show fa neighbor",
    ),

    MigrationStep(
        number=13,
        key="config_internet",
        name="Configure Internet Exit (VLAN 100, Port 1)",
        phase=Phase.PHASE_2_FABRIC,
        applies_to=["SW1", "SW2"],
        description=(
            "Create VLAN 100 (Internet_Exit), add Port 1 (modem port), assign IP. "
            "SW1: 192.168.1.2/24 — SW2: 192.168.1.3/24. "
            "Default route to modem 192.168.1.1. "
            "Both switches have independent internet exit — Option A resilient fabric."
        ),
        exos_parallel=(
            "EXOS lab: `configure iproute add default 192.168.1.1`. "
            "VOSS syntax: `ip route 0.0.0.0 0.0.0.0 192.168.1.1 weight 1 enable`. "
            "Weight 1 and `enable` keyword are required — route is inactive without them."
        ),
        standard="RFC 1812 — static default route; weight keyword for ECMP tie-breaking",
        expected_commands={
            "SW1": [
                "vlan create 100 name Internet_Exit type port-mstprstp 0",
                "vlan members add 100 1/1",
                "interface vlan 100",
                "ip address 192.168.1.2/24",
                "exit",
                "ip route 0.0.0.0 0.0.0.0 192.168.1.1 weight 1 enable",
            ],
            "SW2": [
                "vlan create 100 name Internet_Exit type port-mstprstp 0",
                "vlan members add 100 1/1",
                "interface vlan 100",
                "ip address 192.168.1.3/24",
                "exit",
                "ip route 0.0.0.0 0.0.0.0 192.168.1.1 weight 1 enable",
            ],
        },
        verification_command="show ip route",
    ),

    MigrationStep(
        number=14,
        key="config_ip_shortcut",
        name="Enable IP Shortcuts (SW2 learns SW1 default route)",
        phase=Phase.PHASE_2_FABRIC,
        applies_to=["SW2"],
        description=(
            "On SW2: `ip-shortcut` under `router isis` redistributes IP prefixes "
            "across the SPB fabric. SW2 automatically learns SW1's default route "
            "without a static route — the fabric IS the routing protocol. "
            "SW1 also needs ip-shortcut to advertise its routes."
        ),
        exos_parallel=(
            "EXOS: you configured a static default route on EACH switch independently. "
            "VOSS ip-shortcut: SW1 advertises 0.0.0.0/0 into IS-IS, SW2 learns it. "
            "If SW1 goes down, SW2 falls back to its own direct modem route."
        ),
        standard="RFC 6329 §5 — IP-shortcut TLV for IS-IS prefix advertisement in SPB",
        expected_commands={
            "SW1": ["router isis", "ip-shortcut", "exit"],
            "SW2": ["router isis", "ip-shortcut", "exit"],
        },
        verification_command="show ip route",
    ),

    MigrationStep(
        number=15,
        key="save_config",
        name="Save Configuration",
        phase=Phase.PHASE_2_FABRIC,
        applies_to=["SW1", "SW2"],
        description=(
            "Save the running config to NVRAM. "
            "VOSS syntax: `save config` (NOT `save configuration` — that's EXOS)."
        ),
        exos_parallel=(
            "EXOS: `save configuration`. VOSS: `save config`. "
            "A common mistake: typing the EXOS command on a VOSS switch gives an error. "
            "The switch will NOT save automatically on reboot."
        ),
        standard="N/A — operational procedure",
        expected_commands={
            "SW1": ["save config"],
            "SW2": ["save config"],
        },
        verification_command="show boot config flags",
    ),

    MigrationStep(
        number=16,
        key="verify_isis",
        name="Verify ISIS Adjacency",
        phase=Phase.PHASE_3_VERIFY,
        applies_to=["SW1", "SW2"],
        description=(
            "Run `show isis adjacency` on both switches. State must be UP (L1L2). "
            "If DOWN: check ethertype, manual-area, system-ID uniqueness, NNI port state. "
            "This is the single most important verification — everything else depends on it."
        ),
        exos_parallel=(
            "EXOS has no IS-IS. Closest analog: `show bgp neighbor` or "
            "`show ospf neighbor` showing FULL/DR state. "
            "ISIS adjacency UP = fabric is live = all I-SIDs are reachable."
        ),
        standard="RFC 6329 — IS-IS adjacency state machine for SPB",
        is_narrative=True,
        expected_commands={},
        verification_command="show isis adjacency",
    ),

    MigrationStep(
        number=17,
        key="verify_fa",
        name="Verify Fabric Attach Assignments",
        phase=Phase.PHASE_3_VERIFY,
        applies_to=["SW1", "SW2"],
        description=(
            "Run `show fa assignment` — all VLANs should show State: ACTIVE, Type: DYNAMIC. "
            "PENDING means the I-SID for that VLAN is not defined. "
            "Empty means the AP has not sent FA requests (check LLDP, auto-sense)."
        ),
        exos_parallel=(
            "EXOS: manually verify `show vlan` to confirm AP port is in the right VLAN. "
            "VOSS FA: the switch shows EXACTLY which VLANs the AP requested and whether "
            "they were granted. Much more visible than EXOS manual trunking."
        ),
        standard="IEEE 802.1Qcj §6 — FA assignment state machine: PENDING → ACTIVE",
        is_narrative=True,
        expected_commands={},
        verification_command="show fa assignment",
    ),

    MigrationStep(
        number=18,
        key="verify_e2e",
        name="Verify E2E Connectivity (4 SSIDs + Internet)",
        phase=Phase.PHASE_3_VERIFY,
        applies_to=["SW1", "SW2"],
        description=(
            "Final verification: connect iPhone to each SSID (Alpha, Bravo, Delta, Gamma). "
            "Each must get a DHCP address and reach the internet. "
            "Check: show ip dhcp-server binding, show application iqagent status (Connected)."
        ),
        exos_parallel=(
            "Identical end-state to the EXOS lab — same 4 SSIDs, same subnets. "
            "The difference: Fabric delivers the VLANs without any manual uplink trunking. "
            "See completed EXOS verification at: "
            "https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/session_log_20260408.html"
        ),
        standard="IEEE 802.1aq + IEEE 802.1Qcj — full E2E service delivery via SPB + FA",
        is_narrative=True,
        expected_commands={},
        verification_command="show ip dhcp-server binding",
    ),
]

# ─── Lookup helpers ───────────────────────────────────────────────────────────

STEPS_BY_KEY: dict[str, MigrationStep] = {s.key: s for s in MIGRATION_STEPS}
STEPS_BY_NUMBER: dict[int, MigrationStep] = {s.number: s for s in MIGRATION_STEPS}


def get_step(number: int) -> MigrationStep:
    return STEPS_BY_NUMBER[number]


def steps_for_switch(switch_id: str) -> list[MigrationStep]:
    return [s for s in MIGRATION_STEPS if switch_id in s.applies_to]
