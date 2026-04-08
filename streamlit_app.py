"""
FabricEngine Flight Simulator — Sprint 1
Streamlit single-page app with 3-plane cockpit view.

Run:  streamlit run streamlit_app.py
Auth: admin / Extreme01!!
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from simulator.models import LabState, MIGRATION_STEPS, get_step
from simulator.models.switch_state import SwitchModel, VlanConfig, SwitchOS
from simulator.services.state_machine_service import StateMachineService
from simulator.services.command_validator import CommandValidatorService
from simulator.services.output_synthesis import OutputSynthesisService
from simulator.services.student_guidance import StudentGuidanceService
from simulator.services.explain_service import ExplainService
from simulator.models.migration_step import THEMES
from simulator.config import (
    EXOS_LAB, STANDARDS_EXOS, STANDARDS_FABRIC, SERVICES, SWITCHES, SPBM
)
from app.export_engine import ExportEngine

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

ADMIN_USER = "admin"
ADMIN_PASS = "Extreme01!!"

PLANE_METADATA = {
    "management": {
        "icon": "🔧",
        "label": "Management Plane",
        "subtitle": "XIQ Intent & Policy Push",
        "color": "#E8F4FD",
        "border": "#326891",
        "standard": "XIQ ZTP+ / HTTPS/SSH config push",
    },
    "control": {
        "icon": "🔄",
        "label": "Control Plane",
        "subtitle": "IS-IS / SPB / Fabric Attach",
        "color": "#E8F8F0",
        "border": "#1a7a3a",
        "standard": "IEEE 802.1aq + RFC 6329 + IEEE 802.1Qcj",
    },
    "data": {
        "icon": "📡",
        "label": "Data Plane",
        "subtitle": "SPB Forwarding / MAC-in-MAC",
        "color": "#F3E8FF",
        "border": "#6B21A8",
        "standard": "IEEE 802.1ah (PBB) + IEEE 802.1aq forwarding",
    },
}

# Per-step plane annotations — what each plane is doing at this step
STEP_PLANE_CONTEXT = {
    1: {  # backup_exos
        "management": ("XIQ: Manage > Devices > Backups > Create Backup\nClone Network Policy: EXOS_Pre_Migration_Backup", "⏳ Pre-migration"),
        "control":    ("EXOS: save configuration as-script sw1_backup.xsf\ncp to USB /usr/local/ext/", "⏳ Pre-migration"),
        "data":       ("No change to data forwarding.\nExisting EXOS VLANs 20/30 (SW1), 50/60 (SW2) still active.", "✅ EXOS active"),
    },
    2: {  # change_os
        "management": ("XIQ: Manage > Devices > Actions > Change OS → VOSS\nSwitch reboots, downloads VOSS image.", "⚠️ Destructive"),
        "control":    ("ALL EXOS config wiped.\nSwitch boots into VOSS/FabricEngine persona.", "⚠️ Config wiped"),
        "data":       ("ALL data forwarding STOPPED.\nNo VLANs, no routes, no AP connectivity during reboot.", "🔴 Traffic down"),
    },
    3: {  # ztp_readopt
        "management": ("XIQ ZTP+: Switch calls home via VLAN 1 DHCP.\nXIQ re-adopts under FabricEngine persona.\nshow application iqagent status → Connected", "⏳ ZTP in progress"),
        "control":    ("IS-IS not yet configured.\nNo fabric adjacency.", "⬛ Not configured"),
        "data":       ("No data services yet.\nSwitch is online but has no VLANs or services.", "⬛ No services"),
    },
    4: {  # config_isis
        "management": ("XIQ: Configure > Network Policy > Switching\n> Common Settings > Enable Fabric Connect\nSet Manual Area: 00.0001", "📋 Policy pending push"),
        "control":    ("CLI: router isis → system-id → manual-area\nIS-IS process configured but NOT yet enabled.\nAdjacency: ⬛ DOWN — hellos not sent yet.", "⬛ Configured, not enabled"),
        "data":       ("SPB topology: not built.\nNo I-SIDs, no fabric paths.\nWaiting for IS-IS adjacency.", "⬛ Waiting for control plane"),
    },
    5: {  # config_spbm
        "management": ("XIQ: Device Template > Port 17 = NNI\nFabric Ethertype: 0x8100 ← CRITICAL\nMust match on both switches.", "📋 Ethertype: 0x8100"),
        "control":    ("CLI: spbm 1 → nick-name → ethertype 0x8100\nSPBM instance configured.\nAdjacency: ⬛ DOWN — ISIS not enabled yet.\n⚠️  Ethertype mismatch = silent drop (most common failure)", "⬛ SPBM configured"),
        "data":       ("MAC-in-MAC (IEEE 802.1ah) encapsulation: not active.\nWaiting for IS-IS to build the SPBM tree.", "⬛ Waiting"),
    },
    6: {  # enable_isis
        "management": ("XIQ: After Complete Config Update is sent,\niqagent triggers 'router isis enable' equivalent.", "📋 Awaiting config push"),
        "control":    ("CLI: router isis enable\nIS-IS process STARTS sending hellos on enabled ports.\nAdjacency: ⏳ INIT — hellos sent, waiting for peer.\n(No port configured yet → adjacency stays DOWN)", "⏳ ISIS starting"),
        "data":       ("SPB forwarding: not active.\nIS-IS must form adjacency before SPB trees are computed.", "⬛ Waiting"),
    },
    7: {  # config_nni
        "management": ("XIQ: Device Template > Port 17 type = NNI\nISIS enabled on NNI port automatically via template.", "📋 NNI port template"),
        "control":    ("CLI: interface gig 1/17 → isis enable → no shutdown\nIS-IS hellos now sent on Port 17.\nAdjacency: ⏳ → ✅ UP when both switches configured!\nRFC 6329: hellos carry SPB TLVs (B-MAC, nick-name)", "⏳ Adjacency forming..."),
        "data":       ("SPB tree computation begins once adjacency is UP.\nMAC-in-MAC paths will be calculated automatically.", "⏳ Path computation pending"),
    },
    8: {  # create_vlans
        "management": ("XIQ: Network Policy > VLANs tab\nCreate VLAN 10/20/30/50/60 with names.", "📋 VLANs in policy"),
        "control":    ("CLI: vlan create — VLANs exist locally.\nNot yet fabric services (I-SIDs not assigned yet).\nFA: AP3000 cannot get VLANs until I-SIDs are bound.", "⬛ Local VLANs only"),
        "data":       ("VLANs created but NOT yet stretched across fabric.\nI-SID binding in next step activates E-LAN service.", "⬛ Local only"),
    },
    9: {  # assign_isids
        "management": ("XIQ: Fabric Attach section > map VLAN → I-SID\nVLAN 20 → I-SID 100020, etc.\nConvention: I-SID = VLAN + 100,000", "📋 FA VLAN→I-SID map"),
        "control":    ("CLI: vlan i-sid 20 100020, etc.\nI-SIDs advertised via IS-IS LSPs (RFC 6329).\nPeer switch learns: 'I-SID 100020 reachable at nick-name 0.00.01'\nAdjacency: ✅ I-SIDs now fabric-stretched!", "✅ E-LAN services active"),
        "data":       ("SPB fabric now carries VLANs as I-SID services.\nIEEE 802.1ah: customer frames encapsulated in backbone MAC + I-SID.\nZero manual VLAN trunking on NNI — Fabric handles it.", "✅ Fabric forwarding active"),
    },
    10: {  # config_iface_vlans
        "management": ("XIQ: IP Interface section > VLAN gateways\nAnycast: same 10.0.X.1 on both switches!\nXIQ pushes identical gateway config to both BEBs.", "📋 Anycast gateways"),
        "control":    ("CLI: interface vlan 20 → ip address 10.0.20.1/24\nip forwarding IMPLICIT — no 'enable ipforwarding' needed!\nL3 gateway active on BOTH switches simultaneously.", "✅ Anycast L3 active"),
        "data":       ("L3 routing: active on all 5 VLANs.\nAnycast: same IP (10.0.X.1) on SW1 and SW2 simultaneously.\nClient uses nearest gateway — optimal path automatically.", "✅ L3 routing active"),
    },
    11: {  # config_dhcp
        "management": ("XIQ: No explicit DHCP config in XIQ Fabric policy.\nDHCP server is CLI-configured on SW1 only.\nSW2 clients reach SW1 DHCP via Fabric relay.", "📋 CLI-only DHCP"),
        "control":    ("CLI: ip dhcp-server enable + pools per VLAN\nSW2 clients get DHCP from SW1 transparently via SPB.\nNo DHCP relay config needed — Anycast handles it.", "✅ DHCP active on SW1"),
        "data":       ("DHCP offers travel via SPB fabric from SW1 to SW2 clients.\nClient on SW2 VLAN 50 gets offer from SW1 pool Delta.", "✅ DHCP via fabric"),
    },
    12: {  # config_fa
        "management": ("XIQ: AP3000 Template > Wired Interface (Eth0)\n> Fabric Attach > map SSID → VLAN → I-SID\nXIQ pushes FA config to AP via HTTPS.", "📋 FA policy in XIQ"),
        "control":    ("CLI: fa enable + interface gig 1/3 auto-sense enable\nAP3000 sends LLDP-FA TLVs (IEEE 802.1Qcj):\n'I need VLAN 20 (I-SID 100020) for SSID Alpha'\nSwitch grants: show fa assignment → ACTIVE DYNAMIC", "✅ FA auto-provisioning"),
        "data":       ("VLAN 20/30 (SW1) + 50/60 (SW2) now active on AP ports.\nNo manual port trunking — AP told switch what it needs.\nSSIDs: Alpha/Bravo/Delta/Gamma now carrying traffic.", "✅ SSIDs active"),
    },
    13: {  # config_internet
        "management": ("XIQ: Port 1 template = Access, VLAN 100 (Internet_Exit).\nDefault route pushed via XIQ template.", "📋 Internet exit port"),
        "control":    ("CLI: vlan 100 → port 1 → ip 192.168.1.2/24\nip route 0.0.0.0 0.0.0.0 192.168.1.1 weight 1 enable\nSW1: direct default route to Quantum Fiber modem.", "✅ SW1 internet route"),
        "data":       ("North-South traffic: client → switch → modem → internet.\nSW1: 192.168.1.2  SW2: 192.168.1.3 (redundant exit).\nBoth switches have independent path to modem.", "✅ Internet path active"),
    },
    14: {  # config_ip_shortcut
        "management": ("XIQ: ip-shortcut is part of ISIS config template.\nPushed automatically when Fabric Connect is enabled.", "📋 Auto-pushed by XIQ"),
        "control":    ("CLI: router isis → ip-shortcut\nSW2 learns SW1's 0.0.0.0/0 route via IS-IS fabric.\nRFC 6329 §5: IP prefix TLVs carry default route info.\nSW2 now has internet via BOTH local modem AND SW1 fabric path.", "✅ IP shortcuts active"),
        "data":       ("SW2 traffic can exit via:\n  1. Local Port 1 → modem (primary)\n  2. NNI → SW1 → modem (failover via ip-shortcut)\nOption A resilience: < 1s convergence on link failure.", "✅ Redundant paths"),
    },
    15: {  # save_config
        "management": ("XIQ: Auto-saves policy. CLI save still required.\nVOSS does NOT auto-save on reboot.", "⚠️ CLI save required"),
        "control":    ("CLI: save config  ← NOT 'save configuration' (that's EXOS!)\nConfig written to NVRAM.\nVerify: show boot config flags", "✅ Config saved"),
        "data":       ("No change to data plane.\nAll services remain active after save.", "✅ All services active"),
    },
    16: {  # verify_isis
        "management": ("XIQ: Manage > Devices > SW1/SW2 topology view\nFabric Attach topology should show fabric link.", "🔍 XIQ topology check"),
        "control":    ("show isis adjacency → State: UP (L1L2)\nshow isis interface → Port 1/17 OperState: Up\nshow spbm → ethertype: 0x8100 on both", "🔍 Verify adjacency"),
        "data":       ("show isis spbm i-sid → confirms East-West I-SID visibility\nshow isis spbm unicast-tree → exact traffic path", "🔍 Verify data paths"),
    },
    17: {  # verify_fa
        "management": ("XIQ: AP3000 shows green in Devices list.\nFA topology visible in XIQ fabric view.", "🔍 XIQ AP status"),
        "control":    ("show fa assignment → State: ACTIVE, Type: DYNAMIC\nshow fa neighbor → AP3000 on Port 1/3\nIf PENDING: I-SID not defined or FA not enabled globally", "🔍 Verify FA"),
        "data":       ("All 4 SSIDs should be forwarding traffic.\nClient on Alpha SSID → VLAN 20 → I-SID 100020 → internet.", "🔍 Verify SSIDs"),
    },
    18: {  # verify_e2e
        "management": ("XIQ: All devices green.\nshow application iqagent status → Connected\nCompare to EXOS baseline: same XIQ org, same APs.", "✅ Full management visibility"),
        "control":    ("show fa assignment → 4 SSIDs ACTIVE\nshow ip dhcp-server binding → 4 clients\nAll services: same as EXOS lab, different architecture.", "✅ All services verified"),
        "data":       ("iPhone on each SSID → DHCP → internet ✅\nE2E path: iPhone → AP3000 (FA) → Switch (I-SID) → NNI (SPB) → modem → internet\nFabric delivers same result as manual EXOS — automatically.", "✅ E2E verified"),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────────────────

def init_session():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "student_name" not in st.session_state:
        st.session_state.student_name = ""
    if "page" not in st.session_state:
        st.session_state.page = "welcome"
    if "lab" not in st.session_state:
        st.session_state.lab = LabState()
    if "sm" not in st.session_state:
        st.session_state.sm = StateMachineService()
    if "guidance" not in st.session_state:
        st.session_state.guidance = StudentGuidanceService()
    if "validator" not in st.session_state:
        st.session_state.validator = CommandValidatorService()
    if "command_history" not in st.session_state:
        st.session_state.command_history = []   # list of {switch, cmd, valid, feedback}
    if "show_output" not in st.session_state:
        st.session_state.show_output = None
    if "last_feedback" not in st.session_state:
        st.session_state.last_feedback = None
    if "active_switch" not in st.session_state:
        st.session_state.active_switch = "SW1"
    if "explain_svc" not in st.session_state:
        st.session_state.explain_svc = ExplainService()
    if "last_explanation" not in st.session_state:
        st.session_state.last_explanation = None


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: apply state updates to SwitchModel
# ─────────────────────────────────────────────────────────────────────────────

def apply_state_updates(updates: dict, switch_id: str, step):
    sw: SwitchModel = st.session_state.lab.switch(switch_id)
    for key, value in updates.items():
        if key == "vlans_to_create":
            for v in value:
                vid = v["vlan_id"]
                if vid not in sw.vlans:
                    sw.vlans[vid] = VlanConfig(vlan_id=vid, name=v["name"])
        elif key == "isids_to_assign":
            for v in value:
                vid = v["vlan_id"]
                if vid in sw.vlans:
                    sw.vlans[vid].isid = v["isid"]
        elif key == "fa_global_enabled":
            sw.fa_global_enabled = value
            if value and 3 not in sw.fa_ports:
                sw.fa_ports.append(3)
        elif key == "nni_isis_enabled":
            sw.nni_isis_enabled = value
        elif key == "nni_no_shutdown":
            sw.nni_no_shutdown = value
        elif hasattr(sw, key):
            setattr(sw, key, value)
    if sw.isis_configured and sw.os == SwitchOS.EXOS:
        sw.os = SwitchOS.VOSS


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: WELCOME
# ─────────────────────────────────────────────────────────────────────────────

def page_welcome():
    st.markdown("""
    <style>
    .hero-rule { border-top: 3px solid #111; margin-bottom: 4px; }
    .hero-thin  { border-top: 1px solid #111; margin-bottom: 16px; }
    .series-label { font-size: 0.65rem; font-weight: 700; letter-spacing: 0.2em;
                    text-transform: uppercase; color: #666; text-align: center; }
    .hero-h1 { font-size: 2.2rem; font-weight: 700; color: #111; line-height: 1.15; }
    .hero-sub { font-size: 1.0rem; font-style: italic; color: #444; }
    .plane-badge { display: inline-block; padding: 2px 10px; border-radius: 3px;
                   font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;
                   text-transform: uppercase; }
    .badge-mgmt  { background: #E8F4FD; color: #326891; border: 1px solid #326891; }
    .badge-ctrl  { background: #E8F8F0; color: #1a7a3a; border: 1px solid #1a7a3a; }
    .badge-data  { background: #F3E8FF; color: #6B21A8; border: 1px solid #6B21A8; }
    .linked-list a { color: #326891; text-decoration: none; font-weight: 600; }
    .linked-list a:hover { text-decoration: underline; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<hr class="hero-rule">', unsafe_allow_html=True)
    st.markdown('<p class="series-label">Extreme Networks Lab Series &nbsp;·&nbsp; FabricEngine / VOSS</p>', unsafe_allow_html=True)
    st.markdown('<hr class="hero-thin">', unsafe_allow_html=True)

    st.markdown('<p class="hero-h1">FabricEngine Flight Simulator</p>', unsafe_allow_html=True)
    st.markdown("""
    <p class="hero-sub">
    A professional-grade simulation environment for engineers migrating a two-switch,
    two-AP lab from EXOS/SwitchEngine to VOSS/FabricEngine — the same environment
    used by astronauts before a mission, or pilots in a 737 simulator before
    touching a real aircraft. Every command you enter here maps directly to a
    configuration that can be pushed to physical hardware via XIQ or CLI.
    </p>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Login / Return (top — so users can skip theory) ───────────────────────
    st.markdown("### Start the Simulation")
    if st.session_state.get("authenticated"):
        sm = st.session_state.get("sm")
        step_num = sm.current_step_number if sm else 1
        st.success(f"✅ Logged in as **{st.session_state.student_name}** — Step {step_num}/18")
        if st.button("↩ Return to Simulator", use_container_width=True, type="primary"):
            st.session_state.page = "simulator"
            st.rerun()
    else:
        with st.form("login_form"):
            name = st.text_input("Your name (for session report)", placeholder="e.g. Khursheed Khan")
            user = st.text_input("Username")
            pwd  = st.text_input("Password", type="password")
            submitted = st.form_submit_button("🚀 Enter the Simulator", use_container_width=True)
            if submitted:
                if user == ADMIN_USER and pwd == ADMIN_PASS:
                    st.session_state.authenticated = True
                    st.session_state.student_name = name or "Lab Engineer"
                    st.session_state.page = "simulator"
                    st.rerun()
                else:
                    st.error("Invalid credentials. Contact your lab administrator.")

    st.markdown("---")

    # ── Theory: What FabricEngine is and how this migration works ─────────────
    st.markdown("### What Is This Migration and Why Does It Matter?")
    st.markdown("""
    <div style="background:#f8fafc;border-left:4px solid #326891;
                padding:20px 24px;border-radius:0 6px 6px 0;
                font-size:0.92rem;line-height:1.8;color:#1e293b">

    <p><b>The situation:</b> You have two Extreme 5320 switches running EXOS/SwitchEngine,
    two AP3000 access points (one on each switch), a Quantum Fiber modem, and four iPhones
    connecting across four SSIDs. Everything works. Now you are migrating the switches
    from EXOS to VOSS/FabricEngine — the same hardware, a different operating system,
    a fundamentally different architecture.</p>

    <p><b>The core difference:</b> In EXOS you were the fabric. You manually trunked every
    VLAN across every uplink, added every VLAN to every AP port, and configured DHCP and
    routing independently on each switch. Every new VLAN meant touching every device.
    In FabricEngine you configure only the <em>edge</em> — the switch port where a
    client or AP connects — and the fabric handles everything in between automatically.
    This is not a small improvement. It changes how you think about the network entirely.</p>

    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### How does a phone actually get an IP address through the fabric?")
    st.markdown("""
    <div style="background:#0f172a;color:#e2e8f0;border-radius:8px;
                padding:20px 24px;font-size:0.88rem;line-height:1.9;margin:8px 0">

    <p style="margin:0 0 12px 0">Follow one iPhone connecting to the Alpha SSID (VLAN 20):</p>

    <table style="width:100%;border-collapse:collapse;font-size:0.85rem">
    <tr><td style="color:#60a5fa;padding:4px 12px 4px 0;white-space:nowrap;vertical-align:top">
        1. Wi-Fi connect</td>
        <td style="color:#e2e8f0;padding:4px 0">iPhone associates with Alpha SSID on AP3000.
        The AP is connected to SW1 Port 3.</td></tr>
    <tr><td style="color:#60a5fa;padding:4px 12px 4px 0;white-space:nowrap;vertical-align:top">
        2. Fabric Attach</td>
        <td style="color:#e2e8f0;padding:4px 0">AP3000 sends an LLDP-FA message to SW1:
        "I need VLAN 20 mapped to I-SID 100020."
        SW1 checks — I-SID 100020 exists — and grants it. Port 3 is now carrying VLAN 20.
        No admin touched that port. No trunk command was typed.</td></tr>
    <tr><td style="color:#60a5fa;padding:4px 12px 4px 0;white-space:nowrap;vertical-align:top">
        3. DHCP Discover</td>
        <td style="color:#e2e8f0;padding:4px 0">iPhone broadcasts DHCP Discover on VLAN 20.
        The frame enters the fabric as I-SID 100020 traffic.</td></tr>
    <tr><td style="color:#60a5fa;padding:4px 12px 4px 0;white-space:nowrap;vertical-align:top">
        4. IS-IS fabric</td>
        <td style="color:#e2e8f0;padding:4px 0">IS-IS (the fabric routing protocol) already knows
        the shortest path between SW1 and SW2 via the NNI link (Port 17).
        Both switches have I-SID 100020 defined, so SW1 is the authoritative DHCP server
        for VLAN 20 — the Anycast Gateway 10.0.20.1 is active on both switches.</td></tr>
    <tr><td style="color:#60a5fa;padding:4px 12px 4px 0;white-space:nowrap;vertical-align:top">
        5. DHCP Offer</td>
        <td style="color:#e2e8f0;padding:4px 0">SW1 DHCP server responds: IP 10.0.20.105,
        gateway 10.0.20.1, DNS 8.8.8.8. iPhone has a working IP address.</td></tr>
    <tr><td style="color:#60a5fa;padding:4px 12px 4px 0;white-space:nowrap;vertical-align:top">
        6. Internet</td>
        <td style="color:#e2e8f0;padding:4px 0">iPhone sends a packet to google.com.
        It goes to 10.0.20.1 (Anycast Gateway on SW1) → default route → VLAN 100 (Internet Exit)
        → Port 1 → Quantum Fiber modem 192.168.1.1 → Internet.</td></tr>
    </table>

    <p style="margin:12px 0 0 0;color:#94a3b8;font-size:0.8rem">
    If the iPhone is on SW2's AP instead: same path, except step 4 uses the IS-IS fabric
    to reach SW1's DHCP server, and internet exits directly via SW2's own Port 1 modem connection.
    Both switches have independent internet exits — this is Option A Resilient Fabric Core.</p>

    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### Why IS-IS? What is SPBM?")
    st.markdown("""
    <div style="background:#f8fafc;border-left:4px solid #1a7a3a;
                padding:18px 24px;border-radius:0 6px 6px 0;
                font-size:0.9rem;line-height:1.8;color:#1e293b;margin:8px 0">

    <p><b>IS-IS</b> (Intermediate System to Intermediate System) is a routing protocol
    that operates at Layer 2 — meaning it can build a network topology map before any
    IP addresses are configured on the switches. This matters because the fabric needs
    to exist before your VLANs and services are layered on top of it.
    IS-IS is what SPB (IEEE 802.1aq) uses as its control plane. RFC 6329 extends IS-IS
    to carry fabric-specific information: which switch has which I-SID, what the backbone
    MAC addresses are, and how to reach each node.</p>

    <p><b>SPBM</b> (Shortest Path Bridging MAC) is the data-plane technology.
    When a frame travels across the NNI link between SW1 and SW2, it is wrapped in a
    MAC-in-MAC header (IEEE 802.1ah) — the original customer frame is encapsulated
    inside a backbone frame. This means the backbone network never needs to learn
    customer MAC addresses. The I-SID in the backbone header identifies which service
    (VLAN) the frame belongs to. When it arrives at the far switch, the backbone header
    is stripped and the original frame is delivered to the right VLAN.</p>

    <p><b>The edge-only configuration principle:</b>
    You configure IS-IS and I-SIDs on the edge switches (BEBs — Backbone Edge Bridges).
    If there were core switches between SW1 and SW2, you would configure only IS-IS
    on those core switches — no VLANs, no services, no DHCP.
    The core just forwards IS-IS topology and carries MAC-in-MAC frames.
    In this two-switch lab, SW1 and SW2 are both edge and core simultaneously.</p>

    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### What is XIQ's Role in All of This?")
    st.markdown("""
    <div style="background:#1e1433;border-left:4px solid #e879f9;
                padding:18px 24px;border-radius:0 6px 6px 0;
                font-size:0.9rem;line-height:1.8;color:#e2e8f0;margin:8px 0">

    <p><b>ExtremeCloud IQ (XIQ)</b> is the cloud management plane that sits above both switches
    and both APs. You can think of it as the intent layer — you describe what you want the network
    to do (VLANs, policies, Fabric Attach mappings, port templates), and XIQ translates that
    intent into CLI commands pushed to each device via the <b>iqagent</b> daemon running on every
    switch and AP.</p>

    <p><b>The iqagent</b> runs continuously on both switches. It is the VOSS equivalent of EXOS's
    ExtremeCloud IQ agent — but in VOSS, it uses a secure HTTPS tunnel back to the XIQ cloud
    controller. You verify it is connected with: <code style="background:#2d1b4e;padding:2px 6px;
    border-radius:3px;font-size:0.82rem">show application iqagent status</code>. If iqagent is
    not Connected, XIQ can see the switch exists but cannot push configuration.</p>

    <p><b>Zero Touch Provisioning Plus (ZTP+)</b> is how a factory-fresh switch re-adopts into XIQ
    after the OS change. The switch boots, gets a DHCP address on VLAN 1, reaches out to the XIQ
    cloud URL, and downloads the device template and network policy assigned to it. You do NOT
    log into the switch manually at this stage — ZTP+ handles the entire onboarding sequence.
    Steps 2 and 3 of this migration are entirely orchestrated by XIQ's ZTP+ process.</p>

    <p><b>What XIQ pushes vs. what you configure in CLI:</b> XIQ manages the structural
    configuration — IS-IS area, SPBM instance, NNI port templates, VLAN definitions,
    Fabric Attach mappings, and AP policies. The DHCP server pools are CLI-only because
    XIQ's FabricEngine policy does not currently expose per-VLAN DHCP pool configuration.
    This is why Step 11 (DHCP) is always done at the CLI, even in a fully XIQ-managed environment.</p>

    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### The 18 Steps as One Sentence Each — The Migration Story")
    story_rows = [
        ("OS-CONVERT",   "1–3",  "#3b82f6",
         "Back up everything, tell XIQ to reformat both switches as FabricEngine, "
         "and wait for them to re-register in XIQ as VOSS devices."),
        ("ISIS-CONTROL", "4–6",  "#22c55e",
         "Give each switch a unique IS-IS identity (system-id), tell them they are in "
         "the same IS-IS area (manual-area 00.0001), configure the SPBM instance "
         "with a matching ethertype, then activate IS-IS so hellos start flowing."),
        ("NNI-LINK",     "7",    "#a855f7",
         "Enable IS-IS on the NNI port (Port 17) between the two switches so they "
         "form an adjacency — once adjacency is UP, the fabric backbone is live."),
        ("VLAN-ISID",    "8–9",  "#f97316",
         "Create the five service VLANs on both switches and bind each one to an I-SID — "
         "this declares the fabric services and makes them reachable across the NNI."),
        ("ANYCAST-DHCP", "10–11","#38bdf8",
         "Assign the same gateway IP to each VLAN on both switches (Anycast Gateway), "
         "then configure SW1 as the single DHCP server — SW2 clients reach it via the fabric automatically."),
        ("ACCESS-FA",    "12–14","#34d399",
         "Enable Fabric Attach on Port 3 so AP3000 self-provisions its VLANs, "
         "create the Internet Exit VLAN on Port 1 with a default route to the modem, "
         "and enable IP Shortcuts so SW2 learns SW1's default route via IS-IS."),
        ("SAVE-VERIFY",  "15–18","#a1a1aa",
         "Save config to NVRAM (VOSS does not auto-save), then verify IS-IS adjacency "
         "is UP, FA assignments are ACTIVE, and all four iPhones get DHCP and reach the internet."),
    ]
    for theme, steps, color, sentence in story_rows:
        st.markdown(
            f"""<div style="display:flex;gap:12px;align-items:flex-start;
                           margin:6px 0;padding:10px 14px;
                           border-left:4px solid {color};background:#fafafa;border-radius:0 5px 5px 0">
              <div style="min-width:110px">
                <div style="color:{color};font-size:0.62rem;font-weight:700;
                            letter-spacing:0.1em;text-transform:uppercase">{theme}</div>
                <div style="color:#888;font-size:0.72rem">Steps {steps}</div>
              </div>
              <div style="color:#1e293b;font-size:0.88rem;line-height:1.6">{sentence}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Learning chain ─────────────────────────────────────────────────────────
    st.markdown("### Learning Path — Linked Context")
    st.markdown("""
    <div class="linked-list">
    <p>This simulator is the <strong>third step</strong> in a continuous learning chain:</p>
    <ol>
      <li><a href="https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/" target="_blank">
          5320 Onboarding — EXOS/SwitchEngine Lab</a>
          — Deploy 2x 5320, 2x AP3000, 4 SSIDs, Quantum Fiber internet
      </li>
      <li><a href="https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/lab_20260329.html" target="_blank">
          Lab Guide (Mar 29 → Apr 8, 2026)</a>
          — Step-by-step XIQ + CLI deployment, verified E2E
      </li>
      <li><a href="https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/session_log_20260408.html" target="_blank">
          April 8 E2E Session</a>
          — 30-minute timed walkthrough, architecture diagrams, verified CLI blocks
      </li>
      <li><strong>← You are here:</strong> FabricEngine Flight Simulator
          — Take everything from Steps 1-3 and rebuild it on VOSS/FabricEngine
      </li>
    </ol>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── The 3-Plane Architecture ───────────────────────────────────────────────
    st.markdown("### What the Simulator Models — Three Planes")
    st.markdown("""
    Every network action in FabricEngine operates across three distinct planes.
    The simulator shows all three simultaneously — like a pilot seeing engine,
    navigation, and systems readouts in one cockpit view.
    """)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div style="background:#E8F4FD;border-left:4px solid #326891;padding:12px;border-radius:4px">
        <strong>🔧 Management Plane</strong><br>
        <em>XIQ Intent & Policy</em><br><br>
        What ExtremeCloud IQ (XIQ) is doing at each step — policy pushes, device templates,
        Fabric Attach configuration, ZTP+ adoption.
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div style="background:#E8F8F0;border-left:4px solid #1a7a3a;padding:12px;border-radius:4px">
        <strong>🔄 Control Plane</strong><br>
        <em>IS-IS / SPB / Fabric Attach</em><br><br>
        What IS-IS (RFC 6329) and Fabric Attach (IEEE 802.1Qcj) are doing —
        adjacency formation, I-SID advertisement, AP auto-provisioning.
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div style="background:#F3E8FF;border-left:4px solid #6B21A8;padding:12px;border-radius:4px">
        <strong>📡 Data Plane</strong><br>
        <em>SPB Forwarding / MAC-in-MAC</em><br><br>
        What IEEE 802.1ah (MAC-in-MAC) is doing — fabric encapsulation,
        I-SID service delivery, traffic forwarding paths.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Topology Diagram ───────────────────────────────────────────────────────
    st.markdown("### Lab Topology")
    topology_text = """\
FabricEngine Lab — Option A Resilient Fabric Core
══════════════════════════════════════════════════

              [ Internet — Quantum Fiber ISP ]
                           |
                   192.168.1.1
               [ Quantum Fiber Modem ]
                  /               \\
           Port1 /                 \\ Port1
      192.168.1.2                   192.168.1.3
  ┌────────────────┐           ┌────────────────┐
  │  SW1 5320-16P  │           │  SW2 5320-16P  │
  │ sys-id 0001    │◄──NNI────►│ sys-id 0002    │
  │ nick: 0.00.01  │  P17-P17  │ nick: 0.00.02  │
  └───────┬────────┘  IS-IS/   └────────┬───────┘
          │ Port3     I-SIDs            │ Port3
  ┌───────▼────────┐  (802.1aq) ┌───────▼───────┐
  │  AP3000-1      │            │  AP3000-2     │
  │  FA Client     │            │  FA Client    │
  │  LLDP-FA TLVs  │            │  LLDP-FA TLVs│
  └───────┬────────┘            └───────┬───────┘
    Alpha VLAN20    Bravo VLAN30   Delta VLAN50   Gamma VLAN60
    10.0.20.x/24   10.0.30.x/24   10.0.50.x/24   10.0.60.x/24
      iPhone 1        iPhone 2       iPhone 3       iPhone 4

XIQ Cloud ─────── iqagent manages both switches + both APs ──────
NNI: IS-IS adjacency (RFC 6329) + I-SID E-LAN services (802.1aq) + MAC-in-MAC (802.1ah)
FA:  Fabric Attach (IEEE 802.1Qcj) — AP auto-provisions VLAN/I-SID, no manual trunk config\
"""
    st.code(topology_text, language=None)

    st.markdown("---")

    # ── 7-Theme Overview ──────────────────────────────────────────────────────
    st.markdown("### Migration Themes — 18 Steps in 7 Functional Groups")
    theme_cols = st.columns(4)
    theme_items = list(THEMES.items())
    for i, (theme_key, meta) in enumerate(theme_items):
        col = theme_cols[i % 4]
        steps_str = ", ".join(str(s) for s in meta["steps"])
        with col:
            st.markdown(
                f"""<div style="background:{meta['color']};border:1px solid {meta['border']};
                            border-radius:6px;padding:10px 12px;margin-bottom:8px">
                  <div style="color:{meta['border']};font-size:0.65rem;font-weight:700;
                              letter-spacing:0.15em;text-transform:uppercase">{theme_key}</div>
                  <div style="color:#e2e8f0;font-size:0.82rem;font-weight:600;margin:3px 0">{meta['label']}</div>
                  <div style="color:#94a3b8;font-size:0.72rem">Steps: {steps_str}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Cisco-EN → VOSS Migration Mapping ─────────────────────────────────────
    with st.expander("🔀 Migration Mapping — Cisco-EN CLI Bins → VOSS Themes", expanded=False):
        st.markdown(
            "The same SOA pattern used in the **Cisco→EXOS CLI Agent** (9 bins) applies here. "
            "These 7 VOSS themes map to the equivalent Cisco-EN functional bins:"
        )
        mapping_rows = [
            ("OS-CONVERT",   "Steps 1–3",  "ONBOARD",         "Factory reset, OS switch, ZTP re-adoption"),
            ("ISIS-CONTROL", "Steps 4–6",  "FAB-SDN",         "IS-IS router, SPBM instance, enable — fabric control plane"),
            ("NNI-LINK",     "Step 7",     "IF-PHYS",         "NNI backbone port — ISIS on port, point-to-point, MTU"),
            ("VLAN-ISID",    "Steps 8–9",  "L2-SEG + FAB-SDN","VLAN creation + I-SID E-LAN service bindings"),
            ("ANYCAST-DHCP", "Steps 10–11","L3-VIRT",         "Anycast gateways (replaces VRRP) + DHCP server"),
            ("ACCESS-FA",    "Steps 12–14","FAB-SDN + L3-VIRT","Fabric Attach, Internet exit, IP shortcuts"),
            ("SAVE-VERIFY",  "Steps 15–18","MGMT-OPS + DIAG-LOG","Save config, verify ISIS/FA/E2E"),
        ]
        hdr = (
            '<table style="width:100%;border-collapse:collapse;font-size:0.82rem">'
            '<thead><tr style="border-bottom:2px solid #ddd;background:#f8f8f8">'
            '<th style="padding:7px 10px;text-align:left">VOSS Theme</th>'
            '<th style="padding:7px 10px;text-align:left">Steps</th>'
            '<th style="padding:7px 10px;text-align:left">Cisco-EN Bin(s)</th>'
            '<th style="padding:7px 10px;text-align:left">What it covers</th>'
            '</tr></thead><tbody>'
        )
        body = ""
        for voss, steps, cisco, desc in mapping_rows:
            meta = THEMES.get(voss, {})
            color = meta.get("border", "#326891")
            body += (
                f'<tr style="border-bottom:1px solid #eee">'
                f'<td style="padding:6px 10px;font-weight:700;color:{color}">{voss}</td>'
                f'<td style="padding:6px 10px;color:#555">{steps}</td>'
                f'<td style="padding:6px 10px;font-family:monospace;font-size:0.78rem;color:#1a7a3a">{cisco}</td>'
                f'<td style="padding:6px 10px;color:#444">{desc}</td>'
                f'</tr>'
            )
        st.markdown(hdr + body + "</tbody></table>", unsafe_allow_html=True)
        st.caption(
            "Cisco-EN CLI Agent: cisco-en-cli-agent-production-fbf7.up.railway.app  ·  "
            "9 bins: ONBOARD · SEC-ID · SYS-INFO · IF-PHYS · L2-SEG · FAB-SDN · L3-VIRT · DIAG-LOG · MGMT-OPS"
        )

    st.markdown("---")

    # ── Standards Reference ────────────────────────────────────────────────────
    with st.expander("📚 Full Standards Reference — EXOS Baseline + FabricEngine Target (click to open)", expanded=False):
        def render_standards_table(standards, phase_label):
            st.markdown(f"**{phase_label}**")
            rows = ""
            for s in standards:
                url = s.get("url", "")
                link = (f'<a href="{url}" target="_blank" style="color:#326891;'
                        f'font-weight:700;text-decoration:none">{s["id"]} ↗</a>'
                        if url else f'<strong>{s["id"]}</strong>')
                rows += (
                    f'<tr><td style="white-space:nowrap;padding:6px 10px">{link}</td>'
                    f'<td style="padding:6px 10px;color:#444">{s["title"]}</td>'
                    f'<td style="padding:6px 10px;color:#555;font-size:0.82rem">{s["relevance"]}</td></tr>\n'
                )
            st.markdown(
                f'<table style="width:100%;border-collapse:collapse;font-size:0.83rem">'
                f'<thead><tr style="border-bottom:2px solid #ddd">'
                f'<th style="text-align:left;padding:6px 10px">Standard</th>'
                f'<th style="text-align:left;padding:6px 10px">Title</th>'
                f'<th style="text-align:left;padding:6px 10px">Relevance to Lab</th>'
                f'</tr></thead><tbody>{rows}</tbody></table>',
                unsafe_allow_html=True,
            )

        render_standards_table(STANDARDS_EXOS, "Phase 1 — EXOS/SwitchEngine Baseline (what you already know)")
        st.markdown("<br>", unsafe_allow_html=True)
        render_standards_table(STANDARDS_FABRIC, "Phase 2 — VOSS/FabricEngine Target (what you are learning)")



# ─────────────────────────────────────────────────────────────────────────────
# PAGE: SIMULATOR
# ─────────────────────────────────────────────────────────────────────────────

def render_plane_row(plane_key: str, step_number: int, lab: LabState):
    """Render one plane row in the 3-plane cockpit view."""
    meta = PLANE_METADATA[plane_key]
    ctx  = STEP_PLANE_CONTEXT.get(step_number, {}).get(plane_key, ("No data for this step.", "–"))
    text, status = ctx

    # Derive live status overlays from LabState
    if plane_key == "control":
        adj = lab.isis_adjacency_up
        adj_str = "✅ **Adjacency UP**" if adj else "⬛ Adjacency DOWN"
        isid_count = min(len(lab.sw1.vlans_with_isids), len(lab.sw2.vlans_with_isids))
        ctrl_live = f"\n\n**Live state:** {adj_str} | I-SIDs active: {isid_count}/5"
    elif plane_key == "data":
        e2e = lab.e2e_connectivity
        fab = lab.fabric_services_visible
        ctrl_live = f"\n\n**Live state:** Fabric services: {'✅ visible' if fab else '⬛ not visible'} | E2E: {'✅ yes' if e2e else '⬛ no'}"
    else:
        iqagent = lab.sw1.isis_enabled or lab.sw2.isis_enabled
        ctrl_live = f"\n\n**Live state:** XIQ iqagent: {'✅ Connected' if iqagent else '⏳ Connecting'}"

    st.markdown(
        f"""
        <div style="background:{meta['color']};border-left:5px solid {meta['border']};
                    padding:14px 16px;border-radius:5px;margin-bottom:8px">
          <strong>{meta['icon']} {meta['label']}</strong>
          &nbsp;<span style="font-size:0.72rem;color:#666">{meta['subtitle']}</span>
          &nbsp;&nbsp;<span style="font-size:0.7rem;color:{meta['border']}">{status}</span>
          <hr style="border:none;border-top:1px solid {meta['border']}33;margin:8px 0">
          <div style="font-size:0.85rem;white-space:pre-wrap">{text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(ctrl_live)


def render_step_tracker():
    """Left sidebar: 18 clickable steps with status icons."""
    sm = st.session_state.sm

    phase_colors = {
        "Phase 1 — OS Conversion":          "#3b82f6",
        "Phase 2 — SPB Fabric + Services":  "#22c55e",
        "Phase 3 — DHCP, Routing, AP Verification": "#a855f7",
    }
    last_phase = None

    for step in MIGRATION_STEPS:
        status = sm.step_status(step.number)
        phase_label = step.phase.value

        # Phase divider
        if phase_label != last_phase:
            phase_short = {"Phase 1 — OS Conversion": "— P1: OS Conversion",
                           "Phase 2 — SPB Fabric + Services": "— P2: Fabric",
                           "Phase 3 — DHCP, Routing, AP Verification": "— P3: Verify"}.get(phase_label, "")
            ph_color = phase_colors.get(phase_label, "#888")
            st.markdown(
                f'<div style="font-size:0.6rem;font-weight:700;color:{ph_color};'
                f'letter-spacing:0.1em;text-transform:uppercase;'
                f'margin:6px 0 2px 0;padding-top:4px;border-top:1px solid #eee">'
                f'{phase_short}</div>',
                unsafe_allow_html=True,
            )
            last_phase = phase_label

        if status == "completed":
            icon, txt_color, bg = "✅", "#1a7a3a", "#f0fdf4"
        elif status == "active":
            icon, txt_color, bg = "▶", "#326891", "#eff6ff"
        else:
            icon, txt_color, bg = "○", "#999", "transparent"

        btn_label = f"{icon} {step.number}. {step.name[:22]}"
        if st.button(
            btn_label,
            key=f"step_btn_{step.number}",
            use_container_width=True,
            help=step.name,
        ):
            sm.jump_to_step(step.number)
            st.session_state.last_feedback = None
            st.session_state.show_output = None
            st.session_state.last_explanation = None
            if step.applies_to:
                st.session_state.active_switch = step.applies_to[0]
            st.rerun()


def render_switch_state_mini(sw: SwitchModel):
    summary = sw.summary_dict()
    cols = st.columns(2)
    items = list(summary.items())
    mid = len(items) // 2
    for i, (k, v) in enumerate(items):
        col = cols[0] if i < mid else cols[1]
        with col:
            icon = "✅" if v not in ("not configured", "off", "none", "no", "not set", "EXOS", "0") else "⬛"
            st.markdown(f'<span style="font-size:0.78rem">{icon} **{k}:** {v}</span>', unsafe_allow_html=True)


def page_simulator():
    lab: LabState = st.session_state.lab
    sm: StateMachineService = st.session_state.sm
    guidance: StudentGuidanceService = st.session_state.guidance
    validator = st.session_state.validator
    output_svc = OutputSynthesisService(lab)

    step = sm.current_step
    sw_id = st.session_state.active_switch

    # ── Live Fabric Status Bar (top of every page) ────────────────────────────
    prog = sm.overall_progress()
    score = guidance.total_score()
    health = lab.health_summary()

    isis_up   = health["ISIS adjacency"] == "UP"
    fab_vis   = lab.fabric_services_visible
    e2e_ok    = lab.e2e_connectivity
    isid_cnt  = min(len(lab.sw1.vlans_with_isids), len(lab.sw2.vlans_with_isids))
    theme_meta = THEMES.get(step.theme, {"border": "#326891", "label": step.theme})

    def _dot(ok): return f'<span style="color:{"#4ade80" if ok else "#f87171"}">{"●" if ok else "○"}</span>'

    st.markdown(
        f"""
        <div style="background:#0f172a;color:#e2e8f0;padding:10px 16px;border-radius:6px;
                    display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;
                    flex-wrap:wrap;gap:6px">
          <span style="font-size:0.85rem;font-weight:700;color:#fff">
            FabricEngine Simulator
            &nbsp;<span style="background:{theme_meta['border']}22;color:{theme_meta['border']};
                   border:1px solid {theme_meta['border']};border-radius:3px;
                   font-size:0.6rem;padding:1px 7px;font-weight:700;letter-spacing:0.1em">
              {step.theme}
            </span>
          </span>
          <span style="font-size:0.82rem;display:flex;gap:16px;flex-wrap:wrap">
            <span>Step <b style="color:#60a5fa">{step.number}/18</b></span>
            <span>{_dot(isis_up)} ISIS {health["ISIS adjacency"]}</span>
            <span>{_dot(isid_cnt==5)} I-SIDs {isid_cnt}/5</span>
            <span>{_dot(fab_vis)} Fabric {"LIVE" if fab_vis else "DOWN"}</span>
            <span>{_dot(e2e_ok)} E2E {"OK" if e2e_ok else "–"}</span>
            <span style="color:#94a3b8">Score <b style="color:#facc15">{score}</b></span>
            <span style="color:#94a3b8">Active <b style="color:#60a5fa">{sw_id}</b></span>
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(prog)

    # ── Layout: Tracker | Main ─────────────────────────────────────────────────
    tracker_col, main_col = st.columns([1, 3])

    with tracker_col:
        # Navigation buttons
        nav_prev, nav_next = st.columns(2)
        with nav_prev:
            if st.button("← Prev", use_container_width=True, disabled=(step.number <= 1)):
                sm.previous_step()
                st.session_state.last_feedback = None
                st.session_state.show_output = None
                st.session_state.last_explanation = None
                st.rerun()
        with nav_next:
            if st.button("Next →", use_container_width=True, disabled=(step.number >= 18)):
                sm.jump_to_step(step.number + 1)
                st.session_state.last_feedback = None
                st.session_state.show_output = None
                st.session_state.last_explanation = None
                st.rerun()

        if st.button("⌂ Landing Page", use_container_width=True, type="secondary"):
            st.session_state.page = "welcome"
            st.rerun()

        st.markdown(
            '<div style="font-size:0.7rem;font-weight:700;color:#888;'
            'letter-spacing:0.1em;text-transform:uppercase;margin:6px 0 2px 0">'
            'Steps</div>',
            unsafe_allow_html=True,
        )
        render_step_tracker()

        st.markdown("---")
        st.markdown(
            '<div style="font-size:0.7rem;font-weight:700;color:#888;'
            'letter-spacing:0.1em;text-transform:uppercase;margin:2px 0">Switch</div>',
            unsafe_allow_html=True,
        )
        sw1_btn = st.button("🔵 SW1", use_container_width=True,
                            type="primary" if sw_id == "SW1" else "secondary")
        sw2_btn = st.button("🟣 SW2", use_container_width=True,
                            type="primary" if sw_id == "SW2" else "secondary")
        if sw1_btn:
            st.session_state.active_switch = "SW1"
            st.rerun()
        if sw2_btn:
            st.session_state.active_switch = "SW2"
            st.rerun()

        st.markdown("---")

        # ── Quick Reference panel ──────────────────────────────────────────────
        with st.expander("📚 References", expanded=False):
            st.markdown("**Lab Links**")
            st.markdown(
                "- [5320 EXOS Lab](https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/)\n"
                "- [Lab Guide Mar 29](https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/lab_20260329.html)\n"
                "- [Apr 8 E2E Session](https://khursheedkhanaiforgood-ai.github.io/5320-onboarding/session_log_20260408.html)"
            )
            st.markdown("**Key Standards**")
            from simulator.config import STANDARDS_FABRIC as _SF
            for s in _SF[:6]:
                url = s.get("url", "")
                if url:
                    st.markdown(f"- [{s['id']}]({url}) — {s['title'].split('(')[0].strip()}")

        with st.expander("🗺 Topology", expanded=False):
            st.code(
                "Internet\n"
                "   |\n"
                "192.168.1.1 Modem\n"
                "  /         \\\n"
                "[SW1]──NNI──[SW2]\n"
                "P17       P17\n"
                "P3          P3\n"
                "[AP1]      [AP2]\n"
                "Alpha/Bravo Delta/Gamma\n"
                "VLAN20/30  VLAN50/60\n"
                "I-SID100020 I-SID100050",
                language=None,
            )

    with main_col:
        # ── Step card with theme badge ─────────────────────────────────────────
        theme_meta = THEMES.get(step.theme, {"label": step.theme, "color": "#1e3a5f", "border": "#326891"})
        std_link = ""
        if step.standard_url:
            std_link = (f' &nbsp;<a href="{step.standard_url}" target="_blank" '
                        f'style="font-size:0.72rem;color:{theme_meta["border"]};'
                        f'text-decoration:none;border-bottom:1px dotted {theme_meta["border"]}">'
                        f'↗ {step.standard.split("—")[0].strip()}</a>')

        st.markdown(
            f"""
            <div style="background:#F7F7F5;border:1px solid #E2E2E2;
                        border-left:5px solid {theme_meta['border']};padding:14px 16px;border-radius:5px">
              <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
                <span style="font-size:0.6rem;font-weight:700;letter-spacing:0.2em;
                              text-transform:uppercase;color:{theme_meta['border']}">
                  Step {step.number}/18 &nbsp;·&nbsp; {step.phase.value}
                </span>
                <span style="background:{theme_meta['color']};color:{theme_meta['border']};
                             border:1px solid {theme_meta['border']};border-radius:4px;
                             font-size:0.6rem;font-weight:700;letter-spacing:0.1em;
                             text-transform:uppercase;padding:2px 8px">
                  {step.theme}
                </span>
              </div>
              <h4 style="margin:0 0 4px 0;color:#111">{step.name}</h4>
              <p style="color:#444;font-size:0.85rem;margin:0 0 4px 0">{step.description}</p>
              <div style="font-size:0.72rem;color:#888">{std_link}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Why? explanation ───────────────────────────────────────────────────
        if step.why:
            with st.expander("💡 Why does this work this way?", expanded=False):
                st.markdown(
                    f'<div style="color:#1e293b;font-size:0.88rem;line-height:1.7">{step.why}</div>',
                    unsafe_allow_html=True,
                )
                if step.standard_url:
                    st.markdown(
                        f'📖 **Standard:** [{step.standard}]({step.standard_url})',
                        unsafe_allow_html=False,
                    )
                st.caption("Type `explain` or `why [concept]` in the CLI box below for a deeper AI explanation.")

        # ══════════════════════════════════════════════════════════════════════
        # ACTION REQUIRED — always first, always visible
        # ══════════════════════════════════════════════════════════════════════
        if step.is_narrative:
            dest_label = "⚠️  DESTRUCTIVE STEP — no undo" if step.is_destructive else "📋  READ & CONFIRM"
            dest_color = "#7f1d1d" if step.is_destructive else "#1e3a5f"
            dest_border = "#ef4444" if step.is_destructive else "#326891"
            st.markdown(
                f"""
                <div style="background:{dest_color};border:2px solid {dest_border};
                            border-radius:8px;padding:18px 20px;margin:12px 0">
                  <div style="color:#fff;font-size:0.72rem;letter-spacing:0.2em;
                              text-transform:uppercase;font-weight:700;margin-bottom:8px">
                    {dest_label}
                  </div>
                  <div style="color:#e2e8f0;font-size:0.95rem;line-height:1.6">
                    {step.description}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                "✅  Confirm & Continue →",
                use_container_width=True,
                type="primary",
                key=f"confirm_narrative_{step.number}",
            ):
                for sid in step.applies_to:
                    sm.mark_confirmed(sid)
                if sm.can_advance():
                    sm.advance()
                    st.session_state.show_output = None
                    st.session_state.last_feedback = None
                    st.session_state.last_explanation = None
                    if not sm.is_complete():
                        next_step = sm.current_step
                        if "SW1" in next_step.applies_to:
                            st.session_state.active_switch = "SW1"
                    else:
                        st.session_state.page = "export"
                st.rerun()

            # Narrative steps also allow explain/why/show (no config commands)
            st.markdown("---")
            st.caption("Ask a question about this step:")
            with st.form(f"narrative_cli_{step.number}", clear_on_submit=True):
                narr_input = st.text_input(
                    "Ask",
                    placeholder="explain  ·  why  ·  why [concept]  ·  show isis adjacency",
                    label_visibility="collapsed",
                )
                narr_submit = st.form_submit_button("Ask →", use_container_width=True)
            if narr_submit and narr_input:
                raw = narr_input.strip()
                lower = raw.lower()
                if lower.startswith("show "):
                    out = OutputSynthesisService(lab).render(lower, sw_id)
                    st.session_state.show_output = out
                    st.session_state.last_explanation = None
                else:
                    explain_svc: ExplainService = st.session_state.explain_svc
                    with st.spinner("Thinking..."):
                        explanation = explain_svc.explain(raw, step, sw_id)
                    st.session_state.last_explanation = explanation
                    st.session_state.show_output = None
                st.rerun()
        else:
            expected_cmds = step.expected_commands.get(sw_id, [])
            prog_obj = sm.step_progress(sw_id)
            next_idx = prog_obj.next_command_index if prog_obj else 0

            # Build command checklist HTML
            cmd_rows = ""
            for i, cmd in enumerate(expected_cmds):
                if prog_obj and i < (next_idx or 0):
                    icon = "✅"
                    style = "color:#4ade80;text-decoration:line-through;opacity:0.7"
                elif i == (next_idx or 0):
                    icon = "▶"
                    style = "color:#fbbf24;font-weight:700"
                else:
                    style = "color:#94a3b8"
                    icon = "○"
                cmd_rows += (
                    f'<div style="font-family:monospace;font-size:0.9rem;'
                    f'padding:4px 0;{style}">'
                    f'{icon}  {cmd}</div>\n'
                )

            st.markdown(
                f"""
                <div style="background:#0f172a;border:2px solid #326891;
                            border-radius:8px;padding:16px 20px;margin:12px 0">
                  <div style="color:#60a5fa;font-size:0.7rem;letter-spacing:0.2em;
                              text-transform:uppercase;font-weight:700;margin-bottom:10px">
                    🖥  TYPE THESE COMMANDS NOW  —  [{sw_id}]  ({next_idx or 0}/{len(expected_cmds)} done)
                  </div>
                  {cmd_rows}
                  <div style="color:#64748b;font-size:0.75rem;margin-top:10px">
                    ▶ = type next · ✅ = done · also: <span style="color:#60a5fa">explain</span> / <span style="color:#60a5fa">why [concept]</span> · show &lt;cmd&gt; · hint · sw1 / sw2
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.form("cli_form", clear_on_submit=True):
                cmd_input = st.text_input(
                    f"[{sw_id}]#",
                    placeholder="VOSS CLI command, show <cmd>, hint, skip, or switch to SW1/SW2",
                    label_visibility="collapsed",
                )
                col_submit, col_hint, col_show = st.columns([2, 1, 1])
                with col_submit:
                    submitted = st.form_submit_button("⏎ Send", use_container_width=True)
                with col_hint:
                    hint_btn = st.form_submit_button("💡 Hint", use_container_width=True)
                with col_show:
                    skip_btn = st.form_submit_button("⏭ Skip step", use_container_width=True)

            if submitted and cmd_input:
                raw = cmd_input.strip()
                lower = raw.lower()

                if lower in ("sw1", "sw2"):
                    st.session_state.active_switch = lower.upper()
                    st.session_state.last_feedback = None
                    st.rerun()

                elif lower in ("explain", "why") or lower.startswith("explain ") or lower.startswith("why "):
                    explain_svc: ExplainService = st.session_state.explain_svc
                    with st.spinner("Thinking..."):
                        explanation = explain_svc.explain(raw, step, sw_id)
                    st.session_state.last_explanation = explanation
                    st.session_state.last_feedback = None
                    st.session_state.show_output = None
                    st.rerun()

                elif lower.startswith("show "):
                    out = output_svc.render(lower, sw_id)
                    st.session_state.show_output = out
                    st.session_state.last_feedback = None
                    st.rerun()

                else:
                    result = validator.validate(raw, step, sw_id, next_idx or 0)
                    guidance.record_attempt(step.number, sw_id, result.valid)

                    st.session_state.command_history.append({
                        "switch": sw_id, "step": step.number,
                        "cmd": raw, "valid": result.valid,
                        "feedback": result.feedback,
                    })
                    st.session_state.last_feedback = result
                    st.session_state.show_output = None

                    if result.valid:
                        sm.mark_command_complete(sw_id, result.command_index)
                        if result.state_updates:
                            apply_state_updates(result.state_updates, sw_id, step)

                        # Auto-advance if step complete
                        if sm.can_advance():
                            sm.advance()
                            st.session_state.last_feedback = None
                            if sm.is_complete():
                                st.session_state.page = "export"
                            else:
                                if "SW1" in sm.current_step.applies_to:
                                    st.session_state.active_switch = "SW1"
                    st.rerun()

            if hint_btn:
                attempts = guidance.attempts_for(step.number, sw_id)
                hint = guidance.get_hint(step, sw_id, attempts)
                tier = 1 if attempts <= 2 else (2 if attempts <= 4 else 3)
                tier_colors = {1: "⚠️", 2: "🟠", 3: "🔴"}
                st.warning(f"{tier_colors[tier]} **Hint (Tier {tier}):** {hint}")

            if skip_btn:
                sm.skip_current_step(sw_id)
                guidance.record_skip(step.number, sw_id)
                if sm.can_advance():
                    sm.advance()
                    st.session_state.last_feedback = None
                    if sm.is_complete():
                        st.session_state.page = "export"
                    else:
                        if "SW1" in sm.current_step.applies_to:
                            st.session_state.active_switch = "SW1"
                st.rerun()

            # ── Feedback ───────────────────────────────────────────────────────
            if st.session_state.last_feedback:
                r = st.session_state.last_feedback
                if r.valid:
                    st.success(f"✅ {r.feedback}")
                elif r.match_type == "partial":
                    st.warning(f"~ {r.feedback}")
                else:
                    st.error(f"✗ {r.feedback}")

        # ── Show output (available for all steps) ─────────────────────────────
        if st.session_state.show_output:
            st.markdown(
                f'<div style="background:#1a1a2e;color:#e2e8f0;font-family:monospace;'
                f'font-size:0.82rem;padding:14px;border-radius:5px;white-space:pre-wrap">'
                f'{st.session_state.show_output}</div>',
                unsafe_allow_html=True,
            )

        # ── AI Explanation (available for all steps) ───────────────────────────
        if st.session_state.last_explanation:
            st.markdown(
                f"""<div style="background:#0f2027;border-left:4px solid #60a5fa;
                               border-radius:6px;padding:14px 16px;margin-top:8px">
                  <div style="color:#60a5fa;font-size:0.65rem;font-weight:700;
                              letter-spacing:0.2em;text-transform:uppercase;margin-bottom:8px">
                    💡 AI Explanation
                  </div>
                  <div style="color:#e2e8f0;font-size:0.88rem;line-height:1.7">
                    {st.session_state.last_explanation}
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button("✕ Clear explanation", key="clear_exp"):
                st.session_state.last_explanation = None
                st.rerun()

        # ── EXOS parallel ──────────────────────────────────────────────────────
        with st.expander("📖 EXOS→VOSS Learning Link", expanded=False):
            st.info(f"**From your EXOS lab:** {step.exos_parallel}")
            st.caption(f"**Standard:** {step.standard}")

        # ── 3-PLANE COCKPIT VIEW ───────────────────────────────────────────────
        with st.expander("✈️ Three-Plane Cockpit View", expanded=True):
            st.caption("All three planes update as you enter commands — same view as real hardware.")
            render_plane_row("management", step.number, lab)
            render_plane_row("control",    step.number, lab)
            render_plane_row("data",       step.number, lab)

        # ── Switch state panels ────────────────────────────────────────────────
        with st.expander("🔵 SW1 State  |  🟣 SW2 State", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**SW1 — 0000.0000.0001**")
                render_switch_state_mini(lab.sw1)
            with c2:
                st.markdown("**SW2 — 0000.0000.0002**")
                render_switch_state_mini(lab.sw2)
            health = lab.health_summary()
            adj_col = "green" if health["ISIS adjacency"] == "UP" else "red"
            st.markdown(
                f'<span style="color:{adj_col};font-weight:700">ISIS adjacency: {health["ISIS adjacency"]}</span>'
                f' &nbsp;|&nbsp; Fabric services: {health["Fabric services visible"]}'
                f' &nbsp;|&nbsp; E2E: {health["E2E connectivity"]}',
                unsafe_allow_html=True,
            )
            if health["Adjacency failure reason"] != "n/a":
                st.error(f"Fault: {health['Adjacency failure reason']}")

        # ── Command history ────────────────────────────────────────────────────
        if st.session_state.command_history:
            with st.expander(f"📋 Command History ({len(st.session_state.command_history)} commands)", expanded=False):
                for entry in reversed(st.session_state.command_history[-20:]):
                    icon = "✅" if entry["valid"] else "❌"
                    color = "#1a7a3a" if entry["valid"] else "#b91c1c"
                    st.markdown(
                        f'<div style="font-family:monospace;font-size:0.8rem;margin:2px 0">'
                        f'<span style="color:{color}">{icon}</span> '
                        f'<b>[{entry["switch"]}]</b> step {entry["step"]}: '
                        f'<code>{entry["cmd"]}</code></div>',
                        unsafe_allow_html=True,
                    )

        # ── Navigation ─────────────────────────────────────────────────────────
        st.markdown("---")
        if st.button("📦 Go to Export / Deploy", use_container_width=False):
            st.session_state.page = "export"
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def page_export():
    lab: LabState = st.session_state.lab
    sm: StateMachineService = st.session_state.sm
    guidance: StudentGuidanceService = st.session_state.guidance
    student_name = st.session_state.student_name

    complete = sm.is_complete()
    score = guidance.total_score()
    max_score = guidance.max_score()

    st.markdown("## 📦 Deploy to Real Hardware")
    st.caption(
        "These artifacts are generated from your simulation session. "
        "They can be applied directly to physical Extreme 5320 switches — "
        "zero delta between simulation and production."
    )

    if complete:
        st.success(f"✅ Simulation complete! Score: **{score}/{max_score}**")
    else:
        remaining = 18 - sm.current_step_number + 1
        st.info(f"Simulation in progress (Step {sm.current_step_number}/18). "
                f"You can export partial configs at any time.")

    exp = ExportEngine(lab, student_name)

    st.markdown("---")
    st.markdown("### 1. CLI Configuration Scripts")
    st.markdown(
        "*Paste directly into VOSS terminal or upload as `.voss` script via XIQ CLI tool.*"
    )
    c1, c2 = st.columns(2)
    with c1:
        sw1_script = exp.cli_script("SW1")
        st.download_button(
            label="⬇️ Download SW1 Config (.voss)",
            data=sw1_script,
            file_name="sw1_fabricengine_config.voss",
            mime="text/plain",
            use_container_width=True,
        )
        with st.expander("Preview SW1 script"):
            st.code(sw1_script, language="bash")
    with c2:
        sw2_script = exp.cli_script("SW2")
        st.download_button(
            label="⬇️ Download SW2 Config (.voss)",
            data=sw2_script,
            file_name="sw2_fabricengine_config.voss",
            mime="text/plain",
            use_container_width=True,
        )
        with st.expander("Preview SW2 script"):
            st.code(sw2_script, language="bash")

    st.markdown("---")
    st.markdown("### 2. XIQ Network Policy (JSON)")
    st.markdown(
        "*Import via XIQ: Configure > Network Policies > Import, "
        "or use XIQ API `POST /xapi/v1/configuration/network-policies`.*"
    )
    xiq_json = exp.xiq_policy_json()
    st.download_button(
        label="⬇️ Download XIQ Policy (JSON)",
        data=xiq_json,
        file_name="fabricengine_xiq_policy.json",
        mime="application/json",
        use_container_width=False,
    )
    with st.expander("Preview XIQ policy JSON"):
        st.json(xiq_json)

    st.markdown("---")
    st.markdown("### 3. Deployment Checklist")
    st.markdown("*Step-by-step verification — the 'pre-flight checklist' before going live.*")
    checklist = exp.deployment_checklist()
    st.download_button(
        label="⬇️ Download Checklist (.txt)",
        data=checklist,
        file_name="fabricengine_deployment_checklist.txt",
        mime="text/plain",
        use_container_width=False,
    )
    with st.expander("Preview checklist"):
        st.code(checklist, language="text")

    st.markdown("---")
    st.markdown("### 4. Score Report")
    report = guidance.report()
    if report["steps"]:
        import pandas as pd
        df = pd.DataFrame(report["steps"])
        df.columns = ["Step", "Switch", "Attempts", "Hints Used", "Skipped", "Score"]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No steps completed yet.")

    st.markdown(f"**Total: {score} / {max_score}**")

    st.markdown("---")
    col_back, col_ref = st.columns(2)
    with col_back:
        if st.button("← Back to Simulator", use_container_width=True):
            st.session_state.page = "simulator"
            st.rerun()
    with col_ref:
        st.markdown(
            f"[📖 View EXOS Source Lab]({EXOS_LAB['landing_page']})"
            f" &nbsp;|&nbsp; "
            f"[📋 Apr 8 E2E Session]({EXOS_LAB['apr8_session']})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="FabricEngine Flight Simulator",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    init_session()

    page = st.session_state.page

    if page == "welcome" or not st.session_state.authenticated:
        page_welcome()
    elif page == "simulator":
        page_simulator()
    elif page == "export":
        page_export()


if __name__ == "__main__":
    main()
