"""
CommandValidatorService — validates student CLI input against expected VOSS commands.

Matching strategy (tiered):
  1. Exact match (normalized whitespace/case)  → full credit, state update applied
  2. Semantic match (known abbreviations)       → full credit with note
  3. Partial match (right family, wrong params) → reject with specific hint
  4. No match                                   → reject with generic direction

State updates: on a valid match, returns a dict of SwitchModel field changes
to be applied by the SimulationEngine. This keeps the validator stateless.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from ..models.migration_step import MigrationStep, MIGRATION_STEPS, get_step
from ..models.switch_state import SwitchModel, VlanConfig
from ..config import SERVICES, SWITCHES, SPBM


@dataclass
class ValidationResult:
    valid: bool
    match_type: str      # "exact", "semantic", "partial", "none"
    feedback: str
    state_updates: Optional[dict] = None   # applied to SwitchModel on valid
    command_index: Optional[int] = None    # which command in the step's list was matched


def _normalize(cmd: str) -> str:
    """Normalize whitespace and lowercase for comparison."""
    return re.sub(r'\s+', ' ', cmd.strip().lower())


# ─── Known VOSS abbreviations (semantic match) ────────────────────────────────
# Maps abbreviated/alternate forms → canonical form
VOSS_ALIASES: dict[str, str] = {
    "int vlan": "interface vlan",
    "int gig": "interface gigabitethernet",
    "int gigabitethernet": "interface gigabitethernet",
    "no shut": "no shutdown",
    "sh isis": "show isis",
    "sh isis adj": "show isis adjacency",
    "sh fa": "show fa assignment",
    "sh vlan": "show vlan",
    "sh ip route": "show ip route",
    "sh run": "show running-config",
    "sh spbm": "show spbm",
}


def _apply_aliases(cmd: str) -> str:
    n = _normalize(cmd)
    for alias, canonical in VOSS_ALIASES.items():
        if n.startswith(alias):
            return canonical + n[len(alias):]
    return n


class CommandValidatorService:
    """
    Validates a student command against the expected commands for the current
    migration step and switch. Returns a ValidationResult with feedback and
    optional state updates.
    """

    def validate(
        self,
        raw_input: str,
        step: MigrationStep,
        switch_id: str,
        next_command_index: int,
    ) -> ValidationResult:
        """
        Validate raw_input against the expected command at next_command_index
        for this step and switch.

        Returns ValidationResult with:
        - valid=True + state_updates if command is accepted
        - valid=False + feedback hint if rejected
        """
        expected_cmds = step.expected_commands.get(switch_id, [])
        if not expected_cmds:
            return ValidationResult(
                valid=False,
                match_type="none",
                feedback=f"No CLI commands expected for {switch_id} in this step.",
            )

        if next_command_index >= len(expected_cmds):
            return ValidationResult(
                valid=False,
                match_type="none",
                feedback="All commands for this step are already complete. Type `next` to advance.",
            )

        expected = _normalize(expected_cmds[next_command_index])
        student = _apply_aliases(raw_input)

        # ── Tier 1: Exact match ───────────────────────────────────────────
        if student == expected:
            return ValidationResult(
                valid=True,
                match_type="exact",
                feedback=f"Correct. ({next_command_index + 1}/{len(expected_cmds)})",
                state_updates=self._derive_state_updates(raw_input.strip(), switch_id, step),
                command_index=next_command_index,
            )

        # ── Tier 2: Semantic match (alias resolved) ───────────────────────
        if _normalize(raw_input) != student and student == expected:
            return ValidationResult(
                valid=True,
                match_type="semantic",
                feedback=f"Accepted (abbreviated form). Canonical: `{expected_cmds[next_command_index]}`",
                state_updates=self._derive_state_updates(raw_input.strip(), switch_id, step),
                command_index=next_command_index,
            )

        # ── Tier 3: Partial match — right command family, wrong params ────
        partial = self._check_partial(student, expected, expected_cmds[next_command_index], switch_id)
        if partial:
            return ValidationResult(valid=False, match_type="partial", feedback=partial)

        # ── Tier 4: No match ──────────────────────────────────────────────
        return ValidationResult(
            valid=False,
            match_type="none",
            feedback=(
                f"Not recognized. Expected: `{expected_cmds[next_command_index]}` "
                f"(step {step.number}: {step.name}). "
                "Type `hint` for guidance."
            ),
        )

    def _check_partial(self, student: str, expected: str, expected_raw: str, switch_id: str) -> str | None:
        """Return a specific correction hint if the command family matches but params are wrong."""

        # system-id: correct command, wrong ID
        if student.startswith("system-id") and expected.startswith("system-id"):
            correct_id = SWITCHES[switch_id]["system_id"]
            return (
                f"Wrong system-ID. For {switch_id} it must be: `system-id {correct_id}` "
                f"(unique per switch — SW1=0000.0000.0001, SW2=0000.0000.0002)"
            )

        # nick-name: correct command, wrong value
        if student.startswith("nick-name") and expected.startswith("nick-name"):
            correct_nn = SWITCHES[switch_id]["nick_name"]
            return f"Wrong nick-name. For {switch_id} use: `nick-name {correct_nn}`"

        # ethertype: right command, wrong value — THIS IS THE #1 FAILURE CAUSE
        if student.startswith("ethertype") and expected.startswith("ethertype"):
            return (
                f"Wrong ethertype. Must be `ethertype {SPBM['ethertype']}` on BOTH switches. "
                "Mismatch causes silent L2 drop — IS-IS hellos never reach the peer."
            )

        # manual-area: right command, wrong value
        if student.startswith("manual-area") and expected.startswith("manual-area"):
            return (
                f"Wrong manual-area. Must be `manual-area {SPBM['manual_area']}` on both switches. "
                "Area mismatch = no ISIS adjacency."
            )

        # vlan i-sid: right command, wrong i-sid
        if student.startswith("vlan i-sid") and expected.startswith("vlan i-sid"):
            # parse expected VLAN and I-SID
            parts = expected.split()
            if len(parts) >= 4:
                vlan_id = parts[2]
                isid = parts[3]
                return (
                    f"Wrong I-SID. For VLAN {vlan_id} use: `vlan i-sid {vlan_id} {isid}` "
                    f"(convention: I-SID = VLAN ID + 100,000)"
                )

        # ip route: default route with wrong syntax
        if student.startswith("ip route") and expected.startswith("ip route"):
            return (
                "Wrong default route syntax. VOSS requires: "
                "`ip route 0.0.0.0 0.0.0.0 192.168.1.1 weight 1 enable` "
                "(both `weight 1` and `enable` are required — route is inactive without them)"
            )

        # save config vs save configuration (EXOS habit)
        if student == "save configuration":
            return "EXOS habit detected. VOSS syntax is `save config` (not `save configuration`)"

        # enable ipforwarding (EXOS habit)
        if "ipforwarding" in student:
            return (
                "EXOS habit: `enable ipforwarding` is not needed in VOSS. "
                "Assigning an IP address to an interface VLAN implicitly enables L3 forwarding."
            )

        return None

    def _derive_state_updates(self, cmd: str, switch_id: str, step: MigrationStep) -> dict:
        """
        Derive SwitchModel field updates from a validated command.
        Returns a flat dict that SimulationEngine applies to the SwitchModel.
        """
        updates = {}
        n = _normalize(cmd)

        if n.startswith("system-id"):
            updates["isis_system_id"] = cmd.split()[-1]
            updates["isis_configured"] = True

        elif n.startswith("manual-area"):
            updates["isis_manual_area"] = cmd.split()[-1]

        elif n == "router isis enable":
            updates["isis_enabled"] = True

        elif n.startswith("nick-name"):
            updates["spbm_nick_name"] = cmd.split()[-1]
            updates["spbm_configured"] = True

        elif n.startswith("ethertype"):
            updates["spbm_ethertype"] = cmd.split()[-1]

        elif n.startswith("isis enable") and step.key == "config_nni":
            updates["nni_isis_enabled"] = True

        elif n == "no shutdown" and step.key == "config_nni":
            updates["nni_no_shutdown"] = True

        elif n.startswith("vlan create"):
            parts = cmd.split()
            # vlan create <id> name <name> type port-mstprstp 0
            try:
                vid = int(parts[2])
                name_idx = parts.index("name") if "name" in parts else None
                vname = parts[name_idx + 1] if name_idx else str(vid)
                updates.setdefault("vlans_to_create", []).append(
                    {"vlan_id": vid, "name": vname}
                )
            except (IndexError, ValueError):
                pass

        elif n.startswith("vlan i-sid"):
            parts = cmd.split()
            try:
                vid = int(parts[2])
                isid = int(parts[3])
                updates.setdefault("isids_to_assign", []).append(
                    {"vlan_id": vid, "isid": isid}
                )
            except (IndexError, ValueError):
                pass

        elif n.startswith("ip address") and step.key == "config_iface_vlans":
            parts = cmd.split()
            if len(parts) >= 3:
                updates["pending_ip"] = parts[2]  # resolved per active interface context

        elif n == "ip dhcp-server enable" and step.key == "config_dhcp":
            updates["dhcp_server_enabled"] = True

        elif n == "fa enable" and step.key == "config_fa":
            updates["fa_global_enabled"] = True

        elif n.startswith("ip route 0.0.0.0"):
            parts = cmd.split()
            if len(parts) >= 5:
                updates["default_route"] = parts[4]

        elif n == "ip-shortcut":
            updates["ip_shortcut_enabled"] = True

        elif n == "save config":
            updates["config_saved"] = True

        return updates
