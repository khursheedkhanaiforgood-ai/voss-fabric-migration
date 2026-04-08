"""
Lab constants for the EXOS → VOSS/FabricEngine Digital Twin Simulator.

Prerequisites: Students should complete the EXOS lab before this simulation.
  - Source lab:     https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/
  - Lab guide:      https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/lab_20260329.html
  - Apr 8 E2E:      https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/session_log_20260408.html

Standards governing this deployment:
  - IEEE 802.1aq   — Shortest Path Bridging (SPB) — control plane architecture
  - RFC 6329       — IS-IS Extensions for SPB
  - IEEE 802.1ah   — Provider Backbone Bridging (MAC-in-MAC) — data plane encapsulation
  - IEEE 802.1Qcj  — Fabric Attach — AP auto-provisioning
  - IEEE 802.1ag   — Connectivity Fault Management (OAM)
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

# ─── Standards Reference ──────────────────────────────────────────────────────
STANDARDS = [
    {"id": "IEEE 802.1aq", "title": "Shortest Path Bridging (SPB)",
     "relevance": "Control plane — IS-IS-based loop-free fabric topology, I-SID service model"},
    {"id": "RFC 6329",     "title": "IS-IS Extensions for IEEE 802.1aq",
     "relevance": "Protocol extensions that carry SPB TLVs inside IS-IS hellos and LSPs"},
    {"id": "IEEE 802.1ah", "title": "Provider Backbone Bridging (PBB / MAC-in-MAC)",
     "relevance": "Data plane encapsulation — customer MAC frames wrapped in backbone MAC + I-SID"},
    {"id": "IEEE 802.1Qcj","title": "Automatic Attachment to Provider Backbone Bridging Services",
     "relevance": "Fabric Attach — AP3000 uses LLDP-FA TLVs to dynamically request VLAN→I-SID bindings"},
    {"id": "IEEE 802.1ag", "title": "Connectivity Fault Management (OAM)",
     "relevance": "End-to-end service OAM — loopback, linktrace, continuity check across Fabric"},
    {"id": "IEEE 802.1D",  "title": "Bridging (spanning tree baseline)",
     "relevance": "SPB replaces STP — no blocked ports, all paths active simultaneously"},
]
