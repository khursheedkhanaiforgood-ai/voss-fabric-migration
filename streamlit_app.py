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

    # ── Simulator description placeholder ─────────────────────────────────────
    st.info(
        "**About This Simulator** — *(Your description goes here — replace this block with your own text)*\n\n"
        "This section is reserved for your introduction to the simulator: what it simulates, "
        "who it is for, and what the student will learn by completing it."
    )

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

    # ── Standards Reference ────────────────────────────────────────────────────
    with st.expander("📚 Full Standards Reference — EXOS Baseline + FabricEngine Target", expanded=False):
        st.markdown("**Phase 1 — EXOS/SwitchEngine Baseline (what you already know)**")
        exos_data = [[s["id"], s["title"], s["relevance"]] for s in STANDARDS_EXOS]
        st.table({"Standard": [r[0] for r in exos_data],
                  "Title": [r[1] for r in exos_data],
                  "Relevance to Lab": [r[2] for r in exos_data]})

        st.markdown("**Phase 2 — VOSS/FabricEngine Target (what you are learning)**")
        fab_data = [[s["id"], s["title"], s["relevance"]] for s in STANDARDS_FABRIC]
        st.table({"Standard": [r[0] for r in fab_data],
                  "Title": [r[1] for r in fab_data],
                  "Relevance to Lab": [r[2] for r in fab_data]})

    st.markdown("---")

    # ── Login ──────────────────────────────────────────────────────────────────
    st.markdown("### Start the Simulation")
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
    """Left sidebar: 18 steps with status icons."""
    sm = st.session_state.sm
    current = sm.current_step_number

    for step in MIGRATION_STEPS:
        status = sm.step_status(step.number)
        if status == "completed":
            icon = "✅"
            style = "color: #1a7a3a; font-size: 0.8rem;"
        elif status == "active":
            icon = "▶️"
            style = "color: #326891; font-weight: 700; font-size: 0.8rem;"
        else:
            icon = "○"
            style = "color: #999; font-size: 0.8rem;"

        phase_short = {"Phase 1 — OS Conversion": "P1",
                       "Phase 2 — SPB Fabric + Services": "P2",
                       "Phase 3 — DHCP, Routing, AP Verification": "P3"}.get(step.phase.value, "")

        st.markdown(
            f'<div style="{style}">{icon} <b>{step.number}</b> {step.name[:28]}</div>',
            unsafe_allow_html=True,
        )


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

    # ── Header bar ────────────────────────────────────────────────────────────
    prog = sm.overall_progress()
    score = guidance.total_score()

    st.markdown(
        f"""
        <div style="background:#111;color:#fff;padding:10px 16px;border-radius:5px;
                    display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="font-size:0.9rem;font-weight:700">
            FabricEngine Flight Simulator
          </span>
          <span style="font-size:0.85rem">
            Step <b>{step.number}</b>/18 &nbsp;|&nbsp;
            <span style="color:#4ade80">{int(prog*100)}%</span> &nbsp;|&nbsp;
            Score: <span style="color:#facc15">{score}</span> &nbsp;|&nbsp;
            Active: <b style="color:#60a5fa">{sw_id}</b>
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(prog)

    # ── Layout: Tracker | Main ─────────────────────────────────────────────────
    tracker_col, main_col = st.columns([1, 3])

    with tracker_col:
        st.markdown("**Migration Steps**")
        render_step_tracker()
        st.markdown("---")
        st.markdown("**Switch context**")
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

    with main_col:
        # ── Step card ──────────────────────────────────────────────────────────
        st.markdown(
            f"""
            <div style="background:#F7F7F5;border:1px solid #E2E2E2;
                        border-left:5px solid #326891;padding:14px 16px;border-radius:5px">
              <span style="font-size:0.62rem;font-weight:700;letter-spacing:0.2em;
                            text-transform:uppercase;color:#326891">
                Step {step.number} / {step.phase.value}
              </span>
              <h4 style="margin:6px 0 4px 0;color:#111">{step.name}</h4>
              <p style="color:#444;font-size:0.85rem;margin:0">{step.description}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── EXOS parallel ──────────────────────────────────────────────────────
        with st.expander("📖 EXOS→VOSS Learning Link", expanded=False):
            st.info(f"**From your EXOS lab:** {step.exos_parallel}")
            st.caption(f"**Standard:** {step.standard}")

        # ── 3-PLANE COCKPIT VIEW ───────────────────────────────────────────────
        st.markdown("### ✈️ Three-Plane Cockpit View")
        st.caption("All three planes update as you enter commands — same view as real hardware.")

        render_plane_row("management", step.number, lab)
        render_plane_row("control",    step.number, lab)
        render_plane_row("data",       step.number, lab)

        # ── Switch state panels ────────────────────────────────────────────────
        with st.expander(f"🔵 SW1 State  |  🟣 SW2 State", expanded=False):
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

        st.markdown("---")

        # ── CLI INPUT AREA ─────────────────────────────────────────────────────
        st.markdown(f"#### [{sw_id}]#  CLI Input")

        if step.is_narrative:
            st.markdown(
                f"*This is a {'⚠️ **destructive**' if step.is_destructive else 'narrative'} step. "
                "Review the cockpit view above and click Confirm to proceed.*"
            )
            if st.button("✅ Confirm & Continue", use_container_width=True):
                for sid in step.applies_to:
                    sm.mark_confirmed(sid)
                if sm.can_advance():
                    sm.advance()
                    st.session_state.show_output = None
                    st.session_state.last_feedback = None
                    if not sm.is_complete():
                        next_step = sm.current_step
                        if "SW1" in next_step.applies_to:
                            st.session_state.active_switch = "SW1"
                    else:
                        st.session_state.page = "export"
                st.rerun()
        else:
            expected_cmds = step.expected_commands.get(sw_id, [])
            prog_obj = sm.step_progress(sw_id)
            next_idx = prog_obj.next_command_index if prog_obj else 0

            if next_idx is not None and next_idx < len(expected_cmds):
                st.caption(f"Next expected command ({next_idx + 1}/{len(expected_cmds)}): "
                           f"`{expected_cmds[next_idx]}`  ← *type below or ask for a hint*")

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

            # ── Show output ────────────────────────────────────────────────────
            if st.session_state.show_output:
                st.markdown(
                    f'<div style="background:#1a1a2e;color:#e2e8f0;font-family:monospace;'
                    f'font-size:0.82rem;padding:14px;border-radius:5px;white-space:pre-wrap">'
                    f'{st.session_state.show_output}</div>',
                    unsafe_allow_html=True,
                )

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
