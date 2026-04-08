"""
StudentGuidanceService — progressive hint system and scoring.

Hints escalate over 3 tiers so students are guided but not immediately given answers.
Scoring rewards completing steps with fewer hints and no skips.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime

from ..models.migration_step import MigrationStep, MIGRATION_STEPS, get_step
from ..config import SWITCHES, SPBM


@dataclass
class StepRecord:
    step_number: int
    switch_id: str
    attempts: int = 0
    hints_used: int = 0
    skipped: bool = False
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    @property
    def score(self) -> int:
        if self.skipped:
            return 60
        base = 100
        base -= min(self.hints_used * 10, 40)
        base -= max(0, (self.attempts - 1)) * 5
        return max(base, 0)


class StudentGuidanceService:

    def __init__(self):
        self._records: dict[tuple[int, str], StepRecord] = {}
        self._total_attempts: dict[tuple[int, str], int] = {}

    def record_attempt(self, step_number: int, switch_id: str, success: bool):
        key = (step_number, switch_id)
        if key not in self._records:
            self._records[key] = StepRecord(step_number=step_number, switch_id=switch_id)
        rec = self._records[key]
        rec.attempts += 1
        if success:
            rec.completed_at = datetime.now()
        self._total_attempts[key] = rec.attempts

    def record_hint_used(self, step_number: int, switch_id: str):
        key = (step_number, switch_id)
        if key not in self._records:
            self._records[key] = StepRecord(step_number=step_number, switch_id=switch_id)
        self._records[key].hints_used += 1

    def record_skip(self, step_number: int, switch_id: str):
        key = (step_number, switch_id)
        if key not in self._records:
            self._records[key] = StepRecord(step_number=step_number, switch_id=switch_id)
        self._records[key].skipped = True
        self._records[key].completed_at = datetime.now()

    def attempts_for(self, step_number: int, switch_id: str) -> int:
        return self._total_attempts.get((step_number, switch_id), 0)

    def get_hint(self, step: MigrationStep, switch_id: str, attempt_count: int) -> str:
        """
        Return a tiered hint. Hint tier escalates with attempt count:
          Tier 1 (attempt 1-2): conceptual direction
          Tier 2 (attempt 3-4): command structure
          Tier 3 (attempt 5+):  exact command shown
        """
        self.record_hint_used(step.number, switch_id)

        if attempt_count <= 2:
            return self._tier1_hint(step, switch_id)
        elif attempt_count <= 4:
            return self._tier2_hint(step, switch_id)
        else:
            return self._tier3_hint(step, switch_id)

    def _tier1_hint(self, step: MigrationStep, switch_id: str) -> str:
        """Conceptual direction — what concept applies here."""
        hints = {
            "backup_exos": "Save your EXOS config before the OS change wipes everything.",
            "change_os": "Use the boot menu or XIQ to change the OS persona. This is destructive.",
            "ztp_readopt": "After reboot, the switch ZTPs into XIQ — same process as your EXOS lab.",
            "config_isis": (
                f"You need to enter the IS-IS routing process and set identifiers for {switch_id}. "
                "ISIS is the control plane for SPB — think of it as the 'brain' that builds the fabric topology."
            ),
            "config_spbm": (
                "SPBM is the data plane of the fabric. "
                "The ethertype must be identical on both switches — mismatch is the #1 failure cause."
            ),
            "enable_isis": "ISIS is configured but not yet running. It needs to be explicitly activated.",
            "config_nni": (
                "The NNI port (Port 17) is where IS-IS hellos travel between the two switches. "
                "Without ISIS enabled on this port, adjacency cannot form."
            ),
            "create_vlans": "Create all 5 service VLANs. Same VLAN IDs on both switches.",
            "assign_isids": (
                "I-SIDs identify services in the SPB fabric (IEEE 802.1aq). "
                "Convention: I-SID = VLAN ID + 100,000."
            ),
            "config_iface_vlans": (
                "Assign IP addresses to the VLAN interfaces. "
                "In VOSS, assigning an IP = routing enabled (no separate `enable ipforwarding` needed)."
            ),
            "config_dhcp": "SW1 is the DHCP server. Enable it globally, then define a pool per VLAN.",
            "config_fa": (
                "Fabric Attach (IEEE 802.1Qcj) lets the AP3000 request its VLANs automatically. "
                "Enable FA globally and on Port 3 with auto-sense."
            ),
            "config_internet": (
                "Create VLAN 100 for internet exit, add Port 1 (modem), assign IP, add default route. "
                "VOSS default route syntax is different from EXOS."
            ),
            "config_ip_shortcut": (
                "ip-shortcut redistributes IP routes through the IS-IS fabric. "
                "SW2 will learn SW1's default route automatically — no static route needed on SW2."
            ),
            "save_config": "VOSS save syntax is different from EXOS. Watch the keyword.",
            "verify_isis": "Run `show isis adjacency` on both switches. State must be UP.",
            "verify_fa": "Run `show fa assignment`. All SSIDs should show ACTIVE + DYNAMIC.",
            "verify_e2e": "Connect an iPhone to each SSID and verify DHCP + internet.",
        }
        return hints.get(step.key, f"Review step {step.number}: {step.name}")

    def _tier2_hint(self, step: MigrationStep, switch_id: str) -> str:
        """Command structure — which CLI mode and command family."""
        hints = {
            "config_isis": (
                "Enter: `router isis` → then set `system-id` and `manual-area` → `exit`\n"
                f"  SW1 system-id: {SWITCHES['SW1']['system_id']}  SW2 system-id: {SWITCHES['SW2']['system_id']}"
            ),
            "config_spbm": (
                f"Enter: `spbm 1` → `nick-name <name>` → `ethertype {SPBM['ethertype']}` → `exit`\n"
                f"  SW1 nick-name: {SWITCHES['SW1']['nick_name']}  SW2 nick-name: {SWITCHES['SW2']['nick_name']}"
            ),
            "enable_isis": "Command: `router isis enable` (top-level, not inside a block)",
            "config_nni": (
                "Enter: `interface gigabitEthernet 1/17` → `isis enable` → "
                "`isis network point-to-point` → `no shutdown` → `exit`"
            ),
            "create_vlans": (
                "Command pattern: `vlan create <id> name <name> type port-mstprstp 0`\n"
                "  IDs: 10=MGMT, 20=Alpha, 30=Bravo, 50=Delta, 60=Gamma"
            ),
            "assign_isids": (
                "Command: `vlan i-sid <vlan_id> <isid>`\n"
                "  VLAN 10 → 100010, VLAN 20 → 100020, VLAN 30 → 100030, "
                "VLAN 50 → 100050, VLAN 60 → 100060"
            ),
            "config_iface_vlans": (
                "Enter: `interface vlan <id>` → `ip address <gateway>/24` → "
                "(`ip dhcp-server enable` if SW1) → `exit`\n"
                "  Gateways: VLAN20=10.0.20.1, VLAN30=10.0.30.1, VLAN50=10.0.50.1, VLAN60=10.0.60.1"
            ),
            "config_dhcp": (
                "Pattern: `ip dhcp-server enable` (global) then for each VLAN:\n"
                "`ip dhcp-server pool <name>` → `network-address` → `range` → `default-router` → `dns-server` → `exit`"
            ),
            "config_fa": (
                "`fa enable` (global)\n"
                "then: `interface gigabitEthernet 1/3` → `auto-sense enable` → `fa enable` → `no shutdown` → `exit`"
            ),
            "config_internet": (
                f"SW1: `ip address 192.168.1.2/24`  SW2: `ip address 192.168.1.3/24`\n"
                f"Default route: `ip route 0.0.0.0 0.0.0.0 192.168.1.1 weight 1 enable`"
            ),
            "config_ip_shortcut": "Enter `router isis` → `ip-shortcut` → `exit`",
            "save_config": "Command: `save config`  (NOT `save configuration` — that's EXOS syntax)",
        }
        return hints.get(step.key, self._tier1_hint(step, switch_id))

    def _tier3_hint(self, step: MigrationStep, switch_id: str) -> str:
        """Exact command — shown after 5+ attempts."""
        cmds = step.expected_commands.get(switch_id, [])
        if cmds:
            cmd_list = "\n  ".join(cmds)
            return (
                f"Exact commands for {switch_id}, step {step.number} ({step.name}):\n"
                f"  {cmd_list}\n"
                "(Standard: " + step.standard + ")"
            )
        return f"This is a narrative step — type `confirm` or press Enter to proceed."

    def total_score(self) -> int:
        return sum(r.score for r in self._records.values())

    def max_score(self) -> int:
        count = sum(len(s.applies_to) for s in MIGRATION_STEPS if not s.is_narrative)
        return count * 100

    def report(self) -> dict:
        return {
            "total_score": self.total_score(),
            "max_score": self.max_score(),
            "steps": [
                {
                    "step": r.step_number,
                    "switch": r.switch_id,
                    "attempts": r.attempts,
                    "hints": r.hints_used,
                    "skipped": r.skipped,
                    "score": r.score,
                }
                for r in sorted(self._records.values(), key=lambda x: (x.step_number, x.switch_id))
            ],
        }
