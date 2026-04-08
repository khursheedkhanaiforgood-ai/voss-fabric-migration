"""
Lab constants for the EXOS → VOSS/FabricEngine Digital Twin Simulator.

Prerequisites: Students should complete the EXOS lab before this simulation.
  - Source lab:     https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/
  - Lab guide:      https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/lab_20260329.html
  - Apr 8 E2E:      https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/session_log_20260408.html

Full standards reference: see STANDARDS_EXOS (Phase 1 baseline) and STANDARDS_FABRIC (Phase 2 target).
Both are combined in STANDARDS_ALL for display in the simulator welcome screen.
"""

# ─── Source Lab (EXOS baseline — student must have completed this first) ──────
EXOS_LAB = {
    "title": "EXOS/SwitchEngine 5320 Lab",
    "description": "Completed EXOS deployment — 2 switches, 2 APs, 4 SSIDs, Quantum Fiber internet",
    "landing_page": "https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/",
    "lab_guide": "https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/lab_20260329.html",
    "apr8_session": "https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/session_log_20260408.html",
    "sw1_ip": "192.168.0.28",
    "sw2_ip": "192.168.0.11",
    "exos_vlans": {
        10: "SW_VLAN_10_Mgmt",
        20: "Corp (SW1)",
        30: "Guest (SW1)",
        50: "Corp2 (SW2)",
        60: "Guest2 (SW2)",
    },
}

# ─── Switch Hardware ───────────────────────────────────────────────────────────
SWITCHES = {
    "SW1": {
        "model": "5320-16P-2MXT-2X",
        "system_id": "0000.0000.0001",
        "nick_name": "0.00.01",
        "exos_ip": "192.168.0.28",
        "exos_vlans": [10, 20, 30],
        "internet_vlan_ip": "192.168.1.2",
        "is_dhcp_server": True,
    },
    "SW2": {
        "model": "5320-16P-2MXT-2X",
        "system_id": "0000.0000.0002",
        "nick_name": "0.00.02",
        "exos_ip": "192.168.0.11",
        "exos_vlans": [10, 50, 60],
        "internet_vlan_ip": "192.168.1.3",
        "is_dhcp_server": False,
    },
}

# ─── Port Assignments ──────────────────────────────────────────────────────────
PORTS = {
    "modem": 1,       # Quantum Fiber (192.168.1.1)
    "ap3000": 3,      # AP3000 PoE+ — Fabric Attach client
    "nni": 17,        # NNI / Fabric backbone (Multi-Gig RJ45)
}

MODEM_IP = "192.168.1.1"

# ─── SPBM Control Plane — MUST match on both switches ─────────────────────────
# RFC 6329: IS-IS Extensions for SPB
# IEEE 802.1aq: SPBM instance 1, ethertype identifies B-TAG frames
SPBM = {
    "instance": 1,
    "ethertype": "0x8100",  # Most common adjacency failure: mismatch here
    "manual_area": "00.0001",
}

# ─── VLAN → I-SID Service Map ─────────────────────────────────────────────────
# Convention: I-SID = VLAN ID + 100,000
# IEEE 802.1aq §12: I-SID identifies an E-LAN service across the SPB fabric
SERVICES = {
    10: {"isid": 100010, "name": "MGMT",  "subnet": "10.0.10.0/24", "gateway": "10.0.10.1", "qos": 6},
    20: {"isid": 100020, "name": "Alpha", "subnet": "10.0.20.0/24", "gateway": "10.0.20.1", "qos": 6},
    30: {"isid": 100030, "name": "Bravo", "subnet": "10.0.30.0/24", "gateway": "10.0.30.1", "qos": 2},
    50: {"isid": 100050, "name": "Delta", "subnet": "10.0.50.0/24", "gateway": "10.0.50.1", "qos": 1},
    60: {"isid": 100060, "name": "Gamma", "subnet": "10.0.60.0/24", "gateway": "10.0.60.1", "qos": 1},
}

# ─── DHCP Pools (SW1 is authoritative; SW2 gets clients via Fabric relay) ─────
DHCP_POOLS = {
    20: {"range_start": "10.0.20.100", "range_end": "10.0.20.200", "gateway": "10.0.20.1"},
    30: {"range_start": "10.0.30.100", "range_end": "10.0.30.200", "gateway": "10.0.30.1"},
    50: {"range_start": "10.0.50.100", "range_end": "10.0.50.200", "gateway": "10.0.50.1"},
    60: {"range_start": "10.0.60.100", "range_end": "10.0.60.200", "gateway": "10.0.60.1"},
}

# ─── Internet Exit ─────────────────────────────────────────────────────────────
INTERNET_EXIT_VLAN = 100
INTERNET_EXIT_NAME = "Internet_Exit"

# ─── Standards Reference — Phase 1: EXOS/SwitchEngine Baseline ───────────────
# These governed the deployed EXOS lab (completed Apr 7-8 2026).
# Reference: https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/
STANDARDS_EXOS = [
    {"id": "IEEE 802.1Q",   "phase": "EXOS",
     "url": "https://www.ieee802.org/1/pages/802.1Q-2018.html",
     "title": "Virtual LANs (VLAN Tagging)",
     "relevance": "802.1Q tags on inter-switch trunk ports — how EXOS VLANs 10/20/30/50/60 traversed the uplink"},
    {"id": "IEEE 802.1D",   "phase": "EXOS",
     "url": "https://www.ieee802.org/1/pages/802.1D-2004.html",
     "title": "MAC Bridges and Spanning Tree Protocol (STP)",
     "relevance": "EXOS ran RSTP (802.1w) to prevent loops — replaced entirely by SPB in VOSS"},
    {"id": "IEEE 802.1w",   "phase": "EXOS",
     "url": "https://www.ieee802.org/1/pages/802.1w-2001.html",
     "title": "Rapid Spanning Tree Protocol (RSTP)",
     "relevance": "EXOS default loop prevention — convergence 1-3s on link failure vs <1s with SPB"},
    {"id": "IEEE 802.1X",   "phase": "EXOS",
     "url": "https://www.ieee802.org/1/pages/802.1x-2010.html",
     "title": "Port-Based Network Access Control",
     "relevance": "EXOS port authentication — XIQ policy enforces 802.1X on Corp VLANs 20/50"},
    {"id": "IEEE 802.3af",  "phase": "EXOS",
     "url": "https://www.ieee802.org/3/af/",
     "title": "Power over Ethernet (PoE) — 15.4W",
     "relevance": "AP3000 powered via PoE on Port 3 each switch — 802.3af/at compliant"},
    {"id": "IEEE 802.3at",  "phase": "EXOS",
     "url": "https://www.ieee802.org/3/at/",
     "title": "Power over Ethernet Plus (PoE+) — 30W",
     "relevance": "5320-16P supports PoE+ — AP3000 draws ~15W, well within budget"},
    {"id": "IEEE 802.11",   "phase": "EXOS",
     "url": "https://www.ieee802.org/11/",
     "title": "Wireless LAN (Wi-Fi — 802.11ax on AP3000)",
     "relevance": "AP3000 is Wi-Fi 6 (802.11ax) — 4 SSIDs (Corp, Guest, Corp2, Guest2)"},
    {"id": "RFC 2131",      "phase": "EXOS",
     "url": "https://www.rfc-editor.org/rfc/rfc2131",
     "title": "Dynamic Host Configuration Protocol (DHCP)",
     "relevance": "EXOS DHCP server per switch — `dhcp-address-range` syntax + port-based enable"},
    {"id": "RFC 1918",      "phase": "EXOS",
     "url": "https://www.rfc-editor.org/rfc/rfc1918",
     "title": "Address Allocation for Private Internets",
     "relevance": "All lab subnets use RFC 1918 space: 10.0.x.0/24 (VOSS target) and 10.10.0.x (EXOS mgmt)"},
    {"id": "RFC 3768",      "phase": "EXOS",
     "url": "https://www.rfc-editor.org/rfc/rfc3768",
     "title": "Virtual Router Redundancy Protocol (VRRP)",
     "relevance": "Not used in EXOS lab — replaced by Anycast Gateway in VOSS (same IP on both BEBs)"},
]

# ─── Standards Reference — Phase 2: VOSS/FabricEngine Target ─────────────────
STANDARDS_FABRIC = [
    {"id": "IEEE 802.1aq",  "phase": "VOSS",
     "url": "https://www.ieee802.org/1/pages/802.1aq.html",
     "title": "Shortest Path Bridging (SPB)",
     "relevance": "Core control plane — IS-IS builds loop-free topology; I-SIDs define E-LAN services across the fabric"},
    {"id": "RFC 6329",      "phase": "VOSS",
     "url": "https://www.rfc-editor.org/rfc/rfc6329",
     "title": "IS-IS Extensions for IEEE 802.1aq",
     "relevance": "Carries SPB TLVs (B-MAC, I-SID, nick-name) inside IS-IS hellos and LSPs on NNI Port 17"},
    {"id": "IEEE 802.1ah",  "phase": "VOSS",
     "url": "https://www.ieee802.org/1/pages/802.1ah.html",
     "title": "Provider Backbone Bridging (PBB — MAC-in-MAC)",
     "relevance": "Data plane — customer MAC frames encapsulated in backbone MAC + 24-bit I-SID; NNI MTU must be ≥1522"},
    {"id": "IEEE 802.1Qcj", "phase": "VOSS",
     "url": "https://www.ieee802.org/1/pages/802.1Qcj-2015.html",
     "title": "Automatic Attachment to Provider Backbone Bridging Services (Fabric Attach)",
     "relevance": "AP3000 sends LLDP-FA TLVs on Port 3 requesting VLAN→I-SID bindings — zero manual port trunking"},
    {"id": "IEEE 802.1ag",  "phase": "VOSS",
     "url": "https://www.ieee802.org/1/pages/802.1ag.html",
     "title": "Connectivity Fault Management (OAM)",
     "relevance": "End-to-end service OAM across the fabric — loopback, linktrace, continuity check per I-SID"},
    {"id": "IEEE 802.1D",   "phase": "VOSS",
     "url": "https://www.ieee802.org/1/pages/802.1D-2004.html",
     "title": "Bridging baseline (superseded by SPB)",
     "relevance": "SPB replaces STP entirely — no blocked ports, all paths active simultaneously (contrast with EXOS RSTP)"},
    {"id": "RFC 6329 §5",   "phase": "VOSS",
     "url": "https://www.rfc-editor.org/rfc/rfc6329#section-5",
     "title": "IS-IS IP Shortcuts for SPB",
     "relevance": "ip-shortcut under router isis — SW2 learns SW1 default route via fabric; no static route needed on SW2"},
    {"id": "RFC 2131",      "phase": "VOSS",
     "url": "https://www.rfc-editor.org/rfc/rfc2131",
     "title": "DHCP (VOSS implementation)",
     "relevance": "VOSS: `ip dhcp-server enable` globally + pool + `ip dhcp-server enable` on interface vlan (TWO enables)"},
    {"id": "IEEE 802.1Qbp", "phase": "VOSS",
     "url": "https://www.ieee802.org/1/pages/802.1Qbp-2014.html",
     "title": "Equal Cost Multiple Path (ECMP) for SPB",
     "relevance": "Both switches connect to Quantum Fiber modem (Port 1) — ECMP over fabric for resilient internet exit"},
    {"id": "IEEE 802.1AB",  "phase": "VOSS",
     "url": "https://www.ieee802.org/1/pages/802.1AB-2016.html",
     "title": "Link Layer Discovery Protocol (LLDP)",
     "relevance": "FA uses LLDP as transport — AP3000 sends FA TLVs via LLDP; must NOT be blocked on Port 3"},
]

# ─── Combined Standards Table (EXOS baseline → VOSS target) ──────────────────
# Used by simulator welcome screen, agent onboarding, and HTML session reports.
# Ordered: EXOS standards first (what student already knows), then VOSS (what's new).
STANDARDS_ALL = STANDARDS_EXOS + STANDARDS_FABRIC

# Backward-compat alias (used in simulator_ui.py)
STANDARDS = STANDARDS_ALL
