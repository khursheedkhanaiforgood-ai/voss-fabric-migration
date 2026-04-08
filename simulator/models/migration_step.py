"""
18-step migration sequence: EXOS/SwitchEngine → VOSS/FabricEngine.

Each MigrationStep includes:
  - description  : what to do
  - why          : WHY this step works this way (the insight layer)
  - theme        : functional bin (7 themes, mirrors Cisco-EN 9-bin pattern)
  - standard     : governing IEEE/RFC text
  - standard_url : clickable link to the actual standard document
  - exos_parallel: learning link back to the EXOS lab

Learning path: student has completed the EXOS lab at
  https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class Phase(str, Enum):
    PHASE_1_OS     = "Phase 1 — OS Conversion"
    PHASE_2_FABRIC = "Phase 2 — SPB Fabric + Services"
    PHASE_3_VERIFY = "Phase 3 — DHCP, Routing, AP Verification"


# ── Functional themes (mirrors Cisco-EN 9-bin pattern) ────────────────────────
# Each theme scopes the ExplainService prompt and colors the step card.

THEMES = {
    "OS-CONVERT":   {"label": "OS Conversion",          "color": "#1e3a5f", "border": "#3b82f6", "steps": [1, 2, 3]},
    "ISIS-CONTROL": {"label": "IS-IS Control Plane",    "color": "#14532d", "border": "#22c55e", "steps": [4, 5, 6]},
    "NNI-LINK":     {"label": "NNI Backbone Link",      "color": "#4a1d96", "border": "#a855f7", "steps": [7]},
    "VLAN-ISID":    {"label": "VLAN / I-SID Services",  "color": "#7c2d12", "border": "#f97316", "steps": [8, 9]},
    "ANYCAST-DHCP": {"label": "Anycast Gateway + DHCP", "color": "#0c4a6e", "border": "#38bdf8", "steps": [10, 11]},
    "ACCESS-FA":    {"label": "Fabric Attach + Routing","color": "#064e3b", "border": "#34d399", "steps": [12, 13, 14]},
    "SAVE-VERIFY":  {"label": "Save + Verify",          "color": "#27272a", "border": "#a1a1aa", "steps": [15, 16, 17, 18]},
}


@dataclass
class MigrationStep:
    number: int
    key: str
    name: str
    phase: Phase
    theme: str                            # one of THEMES keys
    applies_to: list[str]
    description: str
    why: str                              # WHY explanation — the insight layer
    exos_parallel: str
    standard: str
    standard_url: str = ""               # clickable link to IEEE / IETF document
    is_destructive: bool = False
    is_narrative: bool = False
    expected_commands: dict[str, list[str]] = field(default_factory=dict)
    verification_command: str = ""


# ─── The 18 Steps ─────────────────────────────────────────────────────────────

MIGRATION_STEPS: list[MigrationStep] = [

    # ── THEME: OS-CONVERT (Steps 1–3) ──────────────────────────────────────────

    MigrationStep(
        number=1,
        key="backup_exos",
        name="Backup EXOS Configuration",
        phase=Phase.PHASE_1_OS,
        theme="OS-CONVERT",
        applies_to=["SW1", "SW2"],
        description=(
            "Save the running EXOS config before the OS change wipes everything. "
            "USB export + XIQ backup. This config is your rollback path."
        ),
        why=(
            "The OS change reformats the switch's storage — every config file, event log, "
            "and credential is permanently erased. Without this backup there is no recovery "
            "path if the VOSS migration fails. XIQ also loses switch history on OS change, "
            "so a separate XIQ network policy clone is your second safety net."
        ),
        exos_parallel=(
            "In the EXOS lab you used `save configuration` and XIQ Backups. "
            "Here: `save configuration as-script switch1_backup.xsf` + copy to USB."
        ),
        standard="N/A — operational procedure",
        standard_url="",
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
        theme="OS-CONVERT",
        applies_to=["SW1", "SW2"],
        description=(
            "Boot menu (spacebar) → 'Change OS to VOSS', or XIQ: Actions → Change OS. "
            "DESTRUCTIVE — wipes all config, logs, events. Switch reboots into FabricEngine."
        ),
        why=(
            "The 5320 is Universal Hardware — one physical device, two OS personalities (EXOS or VOSS). "
            "The OS switch reformats the storage partition, which is why all config is erased. "
            "XIQ can trigger this remotely via Actions → Change OS, avoiding manual console access. "
            "After reboot the switch boots as FabricEngine (VOSS) and begins ZTP+ discovery."
        ),
        exos_parallel=(
            "In the EXOS lab you used ZTP+ to adopt the switch. After OS change, "
            "ZTP+ runs again from scratch under the VOSS/FabricEngine persona."
        ),
        standard="Extreme 5320 Universal Hardware — dual-persona capability",
        standard_url="https://www.extremenetworks.com/products/switches/5320-series/",
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
        theme="OS-CONVERT",
        applies_to=["SW1", "SW2"],
        description=(
            "After reboot in VOSS persona, the switch ZTPs into XIQ. "
            "Assign to your XIQ org, apply FabricEngine device template."
        ),
        why=(
            "After the OS change the switch has no config — it is a blank FabricEngine node. "
            "ZTP+ discovers ExtremeCloud IQ via DHCP option 43 on VLAN 1 and self-registers. "
            "No manual IP address or console session is needed as long as the upstream DHCP "
            "provides the XIQ URL. The FabricEngine device template in XIQ pre-stages port roles "
            "(NNI, Auto-Sense, Access) before you apply CLI config."
        ),
        exos_parallel=(
            "Identical process to the EXOS lab onboarding at "
            "https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/ — "
            "same XIQ org, same DHCP discovery via VLAN 1."
        ),
        standard="XIQ ZTP+ — same discovery flow regardless of EXOS or VOSS persona",
        standard_url="https://extremecloudiq.com/",
        is_narrative=True,
        expected_commands={},
        verification_command="show application iqagent status",
    ),

    # ── THEME: ISIS-CONTROL (Steps 4–6) ────────────────────────────────────────

    MigrationStep(
        number=4,
        key="config_isis",
        name="Configure Router ISIS",
        phase=Phase.PHASE_2_FABRIC,
        theme="ISIS-CONTROL",
        applies_to=["SW1", "SW2"],
        description=(
            "Enter the IS-IS routing process and set the system-ID and manual-area. "
            "system-ID must be UNIQUE per switch. manual-area must be IDENTICAL on both. "
            "RFC 6329: system-ID maps to the IS-IS NET address in SPB deployments."
        ),
        why=(
            "SPB (IEEE 802.1aq) mandates IS-IS as its control plane. IS-IS was chosen over OSPF "
            "because it operates at Layer 2 — the fabric topology can be computed before any IP "
            "addresses exist. The system-id is a 6-byte globally unique node identifier (similar "
            "to a MAC address). The manual-area defines the IS-IS Level 1 routing domain — "
            "both switches must share this area to become IS-IS peers."
        ),
        exos_parallel=(
            "EXOS has no ISIS — this is entirely new. In EXOS you used static routes "
            "(`configure iproute add default`). VOSS uses IS-IS to distribute routes "
            "across the fabric automatically via ip-shortcut."
        ),
        standard="RFC 6329 — IS-IS Extensions for IEEE 802.1aq Shortest Path Bridging",
        standard_url="https://www.rfc-editor.org/rfc/rfc6329",
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
        theme="ISIS-CONTROL",
        applies_to=["SW1", "SW2"],
        description=(
            "Configure SPBM instance 1: ethertype 0x8100 and nick-name. "
            "Ethertype MUST match on both switches — mismatch causes silent L2 drop. "
            "Nick-name is the human-readable SPBM node identifier."
        ),
        why=(
            "The SPBM instance is the 'namespace' for the fabric. The nick-name is a short "
            "human-readable label for this switch in the fabric topology (think SPB hostname). "
            "The ethertype (0x8100) is stamped on every backbone-tagged frame so switches can "
            "identify SPB control traffic. If SW1 uses 0x8100 and SW2 uses 0x88A8, IS-IS "
            "adjacency may still form but I-SID traffic silently drops — no error, no log. "
            "This ethertype mismatch is the #1 silent failure in SPB deployments."
        ),
        exos_parallel=(
            "No EXOS equivalent. SPB (IEEE 802.1aq) replaces STP entirely — "
            "instead of blocking ports to prevent loops, IS-IS computes loop-free "
            "shortest-path trees. All ports active simultaneously."
        ),
        standard="IEEE 802.1aq — Shortest Path Bridging (SPBM instance configuration)",
        standard_url="https://www.ieee802.org/1/pages/802.1aq.html",
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
        theme="ISIS-CONTROL",
        applies_to=["SW1", "SW2"],
        description=(
            "Activate the IS-IS process globally. ISIS will not send hellos until enabled. "
            "Configure-then-enable pattern: by design, so you finish all config before "
            "bringing up the control plane."
        ),
        why=(
            "IS-IS must be explicitly activated after configuration. This deliberate two-phase "
            "design (configure → enable) prevents a partially-configured IS-IS from sending "
            "malformed hellos during setup. Before this step IS-IS is silent. After this step "
            "IS-IS begins sending hellos on enabled interfaces. Adjacency will form within "
            "seconds if both switches are properly configured."
        ),
        exos_parallel=(
            "EXOS: no ISIS. Closest analog: `enable ospf` after configuring OSPF areas. "
            "Same separation of configure-then-enable pattern."
        ),
        standard="RFC 6329 §4 — IS-IS control plane activation for SPB",
        standard_url="https://www.rfc-editor.org/rfc/rfc6329#section-4",
        expected_commands={
            "SW1": ["router isis enable"],
            "SW2": ["router isis enable"],
        },
        verification_command="show isis",
    ),

    # ── THEME: NNI-LINK (Step 7) ────────────────────────────────────────────────

    MigrationStep(
        number=7,
        key="config_nni",
        name="Configure NNI Port (Port 17)",
        phase=Phase.PHASE_2_FABRIC,
        theme="NNI-LINK",
        applies_to=["SW1", "SW2"],
        description=(
            "Enable ISIS on the NNI port and set network type to point-to-point. "
            "Port 17 is the Multi-Gig RJ45 — preferred for fabric backbone. "
            "MTU must be ≥1522 to accommodate MAC-in-MAC overhead (IEEE 802.1ah)."
        ),
        why=(
            "The NNI (Network-to-Network Interface) is the SPB backbone link — all I-SID "
            "traffic crosses here. IS-IS hellos are only sent on ISIS-enabled ports. "
            "Point-to-point mode skips DIS (Designated IS) election, which is only needed "
            "when 3+ routers share a broadcast segment. With only 2 switches, P2P mode "
            "gives faster adjacency formation. The MAC-in-MAC encapsulation (IEEE 802.1ah) "
            "adds 18 bytes of backbone header per frame, so standard 1500-byte MTU must be "
            "raised to ≥1522 or large frames will be silently dropped at the NNI."
        ),
        exos_parallel=(
            "In EXOS you manually trunked every VLAN on the inter-switch uplink. "
            "In VOSS: zero VLAN config on NNI — I-SIDs flow automatically once ISIS "
            "adjacency is UP. This is the 'zero-config NNI' advantage of SPB."
        ),
        standard="IEEE 802.1ah — Provider Backbone Bridging (MAC-in-MAC); NNI MTU ≥1522",
        standard_url="https://www.ieee802.org/1/pages/802.1ah.html",
        expected_commands={
            "SW1": ["interface gigabitEthernet 1/17", "isis enable", "isis network point-to-point", "no shutdown", "exit"],
            "SW2": ["interface gigabitEthernet 1/17", "isis enable", "isis network point-to-point", "no shutdown", "exit"],
        },
        verification_command="show isis interface",
    ),

    # ── THEME: VLAN-ISID (Steps 8–9) ───────────────────────────────────────────

    MigrationStep(
        number=8,
        key="create_vlans",
        name="Create VLANs 10/20/30/50/60",
        phase=Phase.PHASE_2_FABRIC,
        theme="VLAN-ISID",
        applies_to=["SW1", "SW2"],
        description=(
            "Create the five service VLANs on both switches. VLANs must exist before "
            "I-SID binding. The fabric service is only active when the corresponding "
            "I-SID is defined on BOTH Backbone Edge Bridges (BEBs)."
        ),
        why=(
            "In VOSS, VLANs are local constructs — they do not automatically span the fabric. "
            "The E-LAN service (created by the I-SID binding in Step 9) is what stretches the "
            "VLAN across the SPB fabric. But the VLAN must exist before an I-SID can be bound "
            "to it. Both BEBs (SW1 and SW2) must have matching VLAN/I-SID pairs, otherwise the "
            "E-LAN service is only half-defined and no traffic crosses the fabric for that VLAN."
        ),
        exos_parallel=(
            "EXOS: `create vlan Corp tag 20`. VOSS: `vlan create 20 name Alpha type port-mstprstp 0`. "
            "Same concept — the I-SID binding in Step 9 is what makes this a Fabric service "
            "instead of a local VLAN."
        ),
        standard="IEEE 802.1aq §12 — BEB VLAN-to-I-SID service binding",
        standard_url="https://www.ieee802.org/1/pages/802.1aq.html",
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
        theme="VLAN-ISID",
        applies_to=["SW1", "SW2"],
        description=(
            "Bind each VLAN to its I-SID (convention: I-SID = VLAN ID + 100,000). "
            "This defines an E-LAN service. Once both BEBs have the same VLAN→I-SID "
            "binding, traffic is automatically forwarded across the fabric."
        ),
        why=(
            "The I-SID (Instance Service ID) is a 24-bit identifier that names an E-LAN service "
            "across the entire SPB fabric. Think of it as a 'virtual wire' between two switch ports "
            "anywhere in the fabric. The VLAN+100,000 convention (e.g. VLAN 20 → I-SID 100020) is "
            "a common practice to make I-SIDs traceable — not a standard requirement. Once both "
            "BEBs have the same VLAN→I-SID binding, the fabric handles distribution automatically. "
            "Fabric Attach (Step 12) also uses these I-SIDs to auto-assign VLANs to AP ports."
        ),
        exos_parallel=(
            "No EXOS equivalent. In EXOS you trunked VLANs manually across every uplink. "
            "I-SIDs eliminate that entirely — define once, fabric handles distribution. "
            "FA (IEEE 802.1Qcj) also uses I-SIDs to auto-assign VLANs to AP ports."
        ),
        standard="IEEE 802.1aq §12.5 — I-SID: 24-bit service instance identifier for E-LAN/E-Line",
        standard_url="https://www.ieee802.org/1/pages/802.1aq.html",
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

    # ── THEME: ANYCAST-DHCP (Steps 10–11) ──────────────────────────────────────

    MigrationStep(
        number=10,
        key="config_iface_vlans",
        name="Configure Interface VLANs (Anycast Gateways)",
        phase=Phase.PHASE_2_FABRIC,
        theme="ANYCAST-DHCP",
        applies_to=["SW1", "SW2"],
        description=(
            "Assign the SAME IP (e.g. 10.0.20.1/24) to VLAN 20 on BOTH switches — Anycast Gateway. "
            "Clients always use 10.0.20.1 regardless of which switch they connect to. "
            "Note: `ip forwarding` is IMPLICIT in VOSS — assigning an IP activates L3 routing."
        ),
        why=(
            "The Anycast Gateway solves the 'which switch is my gateway?' problem without VRRP. "
            "With VRRP (old approach), one switch is active and the other is standby — wasted capacity. "
            "With Anycast, BOTH switches are always active gateways with identical IPs. The client "
            "never notices which switch handles its traffic. This also means failover is instantaneous — "
            "no VRRP election needed. Critical EXOS→VOSS difference: VOSS activates IP forwarding "
            "automatically when you assign an IP to an interface vlan. Never type `enable ipforwarding` "
            "on VOSS — it does not exist and will error."
        ),
        exos_parallel=(
            "EXOS: `configure vlan Corp ipaddress 10.0.20.1/24` + `enable ipforwarding vlan Corp`. "
            "VOSS: `interface vlan 20` → `ip address 10.0.20.1/24` — NO `enable ipforwarding` needed. "
            "SVIs are 10.0.x.1 in VOSS (not 10.10.0.x as in your EXOS lab)."
        ),
        standard="IEEE 802.1aq — BEB L3 Anycast Gateway; ip forwarding implicit per VOSS design",
        standard_url="https://www.ieee802.org/1/pages/802.1aq.html",
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
        theme="ANYCAST-DHCP",
        applies_to=["SW1"],
        description=(
            "SW1 is the authoritative DHCP server for all VLANs. SW2 clients reach SW1 DHCP "
            "via the SPB fabric — no DHCP relay config needed because Anycast Gateways handle "
            "L3 forwarding transparently."
        ),
        why=(
            "A single DHCP server (SW1) simplifies management — one place to manage address pools. "
            "SW2 clients can reach SW1's DHCP server because the Anycast Gateway on SW2 "
            "forwards DHCP discover/request packets across the I-SID to SW1. No ip helper-address "
            "or DHCP relay is needed. VOSS requires TWO separate `ip dhcp-server enable` commands: "
            "one globally (`ip dhcp-server enable`) and one per interface vlan. Missing either one "
            "is the most common DHCP failure on VOSS."
        ),
        exos_parallel=(
            "EXOS: `configure vlan Corp dhcp-address-range 10.0.20.100 10.0.20.200` "
            "+ `enable dhcp ports 3 vlan Corp`. "
            "VOSS: `ip dhcp-server enable` globally + pool per VLAN + "
            "`ip dhcp-server enable` under `interface vlan`. Two separate enables."
        ),
        standard="RFC 2131 — Dynamic Host Configuration Protocol; VOSS two-enable pattern",
        standard_url="https://www.rfc-editor.org/rfc/rfc2131",
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

    # ── THEME: ACCESS-FA (Steps 12–14) ─────────────────────────────────────────

    MigrationStep(
        number=12,
        key="config_fa",
        name="Configure Fabric Attach (Port 3 — AP3000)",
        phase=Phase.PHASE_2_FABRIC,
        theme="ACCESS-FA",
        applies_to=["SW1", "SW2"],
        description=(
            "Enable Fabric Attach globally and on Port 3 with auto-sense. "
            "The AP3000 uses LLDP-FA TLVs (IEEE 802.1Qcj) to request VLAN→I-SID bindings. "
            "auto-sense enables the port to accept FA requests dynamically — "
            "no manual VLAN trunking needed on the AP port."
        ),
        why=(
            "Fabric Attach (IEEE 802.1Qcj) makes the AP3000 self-provisioning. The AP sends LLDP-FA "
            "TLVs saying 'I need VLAN 20 on I-SID 100020 and VLAN 30 on I-SID 100030.' The switch "
            "checks if the I-SID exists (it does — from Step 9) and grants the assignment. "
            "The admin configures `auto-sense enable` + `fa enable` once and never manually touches "
            "the port for VLAN changes. This eliminates the #1 EXOS admin task: manually trunking "
            "every VLAN on every AP port every time a VLAN is added. FA assignments are LLDP-driven "
            "so LLDP must NOT be blocked on Port 3."
        ),
        exos_parallel=(
            "EXOS: `configure vlan Corp add ports 3 tagged` (manual for every VLAN). "
            "VOSS FA: zero manual config on AP port — the AP tells the switch which VLANs it needs "
            "via LLDP-FA TLVs. Same result, but AP-driven instead of admin-driven."
        ),
        standard="IEEE 802.1Qcj — Automatic Attachment to Provider Backbone Bridging Services (Fabric Attach)",
        standard_url="https://www.ieee802.org/1/pages/802.1Qcj-2015.html",
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
        theme="ACCESS-FA",
        applies_to=["SW1", "SW2"],
        description=(
            "Create VLAN 100 (Internet_Exit), add Port 1 (modem port), assign IP. "
            "SW1: 192.168.1.2/24 — SW2: 192.168.1.3/24. Default route to 192.168.1.1. "
            "Both switches have independent internet exit — Option A resilient fabric."
        ),
        why=(
            "Option A Resilient Fabric Core: both switches connect directly to the Quantum Fiber modem. "
            "SW1 uses 192.168.1.2, SW2 uses 192.168.1.3 — independent L3 uplinks. "
            "The `weight 1 enable` syntax is critical: VOSS static routes are inactive by default "
            "without the `enable` keyword. Missing it means the route exists in config but does not "
            "install in the routing table — traffic is silently dropped. "
            "The `weight` parameter is required for ECMP tie-breaking when multiple equal-cost routes exist."
        ),
        exos_parallel=(
            "EXOS: `configure iproute add default 192.168.1.1`. "
            "VOSS: `ip route 0.0.0.0 0.0.0.0 192.168.1.1 weight 1 enable`. "
            "Weight 1 and `enable` keyword are required — route is inactive without them."
        ),
        standard="RFC 1812 — static default route; weight keyword for ECMP tie-breaking",
        standard_url="https://www.rfc-editor.org/rfc/rfc1812",
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
        theme="ACCESS-FA",
        applies_to=["SW1", "SW2"],
        description=(
            "On both switches: `ip-shortcut` under `router isis` redistributes IP prefixes "
            "across the SPB fabric. SW2 automatically learns SW1's default route — "
            "the fabric IS the routing protocol. SW1 also needs ip-shortcut to advertise."
        ),
        why=(
            "IP-shortcut (RFC 6329 §5) redistributes IP routes into IS-IS TLVs and propagates them "
            "across the SPB fabric. Without it, SW2 only knows its directly connected routes. "
            "With ip-shortcut enabled on SW1, it advertises 0.0.0.0/0 into IS-IS and SW2 learns "
            "it automatically via the fabric — no static route needed on SW2. "
            "If SW1's internet exit fails, SW2 falls back to its own direct modem route automatically. "
            "This is the protocol-driven failover that replaces manual static route management."
        ),
        exos_parallel=(
            "EXOS: you configured a static default route on EACH switch independently. "
            "VOSS ip-shortcut: SW1 advertises 0.0.0.0/0 into IS-IS, SW2 learns it. "
            "If SW1 goes down, SW2 falls back to its own direct modem route automatically."
        ),
        standard="RFC 6329 §5 — IP-shortcut TLV for IS-IS prefix advertisement in SPB",
        standard_url="https://www.rfc-editor.org/rfc/rfc6329#section-5",
        expected_commands={
            "SW1": ["router isis", "ip-shortcut", "exit"],
            "SW2": ["router isis", "ip-shortcut", "exit"],
        },
        verification_command="show ip route",
    ),

    # ── THEME: SAVE-VERIFY (Steps 15–18) ───────────────────────────────────────

    MigrationStep(
        number=15,
        key="save_config",
        name="Save Configuration",
        phase=Phase.PHASE_2_FABRIC,
        theme="SAVE-VERIFY",
        applies_to=["SW1", "SW2"],
        description=(
            "Save the running config to NVRAM. "
            "VOSS syntax: `save config` — NOT `save configuration` (that is EXOS)."
        ),
        why=(
            "VOSS does not auto-save configuration on reboot — if power is lost without saving, "
            "all your work from Steps 4–14 is gone. The command `save config` (abbreviated) "
            "is VOSS syntax. The EXOS command `save configuration` will return an error on VOSS. "
            "This is the most common EXOS muscle-memory mistake and also the most painful if "
            "discovered after a reboot. Always save immediately after completing configuration."
        ),
        exos_parallel=(
            "EXOS: `save configuration`. VOSS: `save config`. "
            "A common mistake: typing the EXOS command on a VOSS switch gives an error. "
            "The switch will NOT save automatically on reboot."
        ),
        standard="N/A — operational procedure",
        standard_url="",
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
        theme="SAVE-VERIFY",
        applies_to=["SW1", "SW2"],
        description=(
            "Run `show isis adjacency` on both switches. State must be UP (L1L2). "
            "If DOWN: check ethertype, manual-area, system-ID uniqueness, NNI port state. "
            "This is the single most important verification — everything else depends on it."
        ),
        why=(
            "IS-IS adjacency is the foundation of the entire fabric. If adjacency is not UP, "
            "no I-SID traffic flows, no FA assignments succeed, no E2E connectivity. "
            "The four common failure causes: (1) ethertype mismatch on SPBM instance, "
            "(2) manual-area mismatch between switches, (3) NNI port not up, "
            "(4) duplicate system-ID. Each has a different `show` command to diagnose. "
            "L1L2 state means the adjacency is up at both IS-IS levels — this is the healthy state for SPB."
        ),
        exos_parallel=(
            "EXOS has no IS-IS. Closest analog: `show bgp neighbor` or `show ospf neighbor` "
            "showing FULL/DR state. ISIS adjacency UP = fabric is live = all I-SIDs are reachable."
        ),
        standard="RFC 6329 — IS-IS adjacency state machine for SPB",
        standard_url="https://www.rfc-editor.org/rfc/rfc6329",
        is_narrative=True,
        expected_commands={},
        verification_command="show isis adjacency",
    ),

    MigrationStep(
        number=17,
        key="verify_fa",
        name="Verify Fabric Attach Assignments",
        phase=Phase.PHASE_3_VERIFY,
        theme="SAVE-VERIFY",
        applies_to=["SW1", "SW2"],
        description=(
            "Run `show fa assignment` — all VLANs should show State: ACTIVE, Type: DYNAMIC. "
            "PENDING means the I-SID for that VLAN is not defined. "
            "Empty means the AP has not sent FA requests (check LLDP, auto-sense)."
        ),
        why=(
            "FA assignment state is the observable record of what the AP3000 requested and what "
            "the switch granted. ACTIVE = the I-SID binding exists and traffic can flow. "
            "PENDING = the AP requested a VLAN/I-SID pair but the I-SID is not defined on this switch "
            "(missing `vlan i-sid` from Step 9). Empty = the AP is not sending FA TLVs at all "
            "(check: LLDP blocked on Port 3, or `auto-sense enable` + `fa enable` missing from Step 12). "
            "FA is much more visible than EXOS manual trunking — you can see exactly what the AP asked for."
        ),
        exos_parallel=(
            "EXOS: manually verify `show vlan` to confirm AP port is tagged in the right VLAN. "
            "VOSS FA: `show fa assignment` shows EXACTLY which VLANs the AP requested and their state. "
            "Much more explicit than EXOS manual trunking verification."
        ),
        standard="IEEE 802.1Qcj §6 — FA assignment state machine: PENDING → ACTIVE",
        standard_url="https://www.ieee802.org/1/pages/802.1Qcj-2015.html",
        is_narrative=True,
        expected_commands={},
        verification_command="show fa assignment",
    ),

    MigrationStep(
        number=18,
        key="verify_e2e",
        name="Verify E2E Connectivity (4 SSIDs + Internet)",
        phase=Phase.PHASE_3_VERIFY,
        theme="SAVE-VERIFY",
        applies_to=["SW1", "SW2"],
        description=(
            "Final verification: connect iPhone to each SSID (Alpha, Bravo, Delta, Gamma). "
            "Each must get a DHCP address and reach the internet. "
            "Check: show ip dhcp-server binding, show application iqagent status (Connected)."
        ),
        why=(
            "The E2E test validates the entire protocol chain simultaneously: "
            "iPhone → Wi-Fi 6 (802.11ax) → AP3000 → FA assignment (802.1Qcj) → "
            "I-SID E-LAN service (802.1aq) → IS-IS fabric (RFC 6329) → "
            "MAC-in-MAC forwarding (802.1ah) → Anycast Gateway → "
            "DHCP (RFC 2131) → Internet. "
            "Each of the 4 SSIDs maps to a distinct VLAN/subnet, confirming traffic isolation. "
            "This is the same end-state as the EXOS lab — the Fabric delivers it with zero "
            "manual VLAN trunking on the NNI or AP ports."
        ),
        exos_parallel=(
            "Identical end-state to the EXOS lab — same 4 SSIDs, same subnets. "
            "The difference: Fabric delivers the VLANs without any manual uplink trunking. "
            "See completed EXOS verification: "
            "https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/session_log_20260408.html"
        ),
        standard="IEEE 802.1aq + IEEE 802.1Qcj — full E2E service delivery via SPB + Fabric Attach",
        standard_url="https://www.ieee802.org/1/pages/802.1aq.html",
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
