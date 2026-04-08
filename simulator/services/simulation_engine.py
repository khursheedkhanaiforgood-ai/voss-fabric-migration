"""
SimulationEngine — main loop that orchestrates the migration simulation.

Responsibilities:
  - Initialize all services with the lab state
  - Run the student input loop
  - Dispatch commands to validator or show-output synthesizer
  - Apply state updates to SwitchModel
  - Trigger explanations and advancement
"""

from __future__ import annotations

from ..models.lab_state import LabState
from ..models.switch_state import SwitchModel, VlanConfig
from ..models.migration_step import MigrationStep
from .state_machine_service import StateMachineService
from .command_validator import CommandValidatorService, ValidationResult
from .output_synthesis import OutputSynthesisService
from .student_guidance import StudentGuidanceService
from ..ui.simulator_ui import SimulatorUI


class SimulationEngine:

    def __init__(self, explanation_service=None, session_log_service=None):
        self.lab = LabState()
        self.sm = StateMachineService()
        self.validator = CommandValidatorService()
        self.output = OutputSynthesisService(self.lab)
        self.guidance = StudentGuidanceService()
        self.ui = SimulatorUI()
        self.explain = explanation_service    # optional — None → offline canned text
        self.logger = session_log_service     # optional — None → no HTML log

    def run(self):
        """Main simulation loop."""
        self.ui.print_welcome()
        self.ui.console.input("  Press Enter to begin the migration...")

        while not self.sm.is_complete():
            step = self.sm.current_step
            sw_id = self.lab.active_switch

            self.ui.print_switch_states(self.lab)
            self.ui.print_step_header(step, self.sm, self.guidance.total_score(), sw_id)

            # For narrative/destructive steps: just confirm to advance
            if step.is_narrative:
                self.ui.console.print(
                    f"  [dim]This is a {('destructive' if step.is_destructive else 'narrative')} step. "
                    "Review the description above and type `confirm` to continue.[/dim]"
                )
                while True:
                    raw = self.ui.prompt(sw_id).strip().lower()
                    if raw in ("confirm", "yes", ""):
                        for sid in step.applies_to:
                            self.sm.mark_confirmed(sid)
                        if self.sm.can_advance():
                            self._complete_step(step)
                            break
                    elif raw == "quit":
                        self._handle_quit()
                        return
                    elif raw.startswith("show "):
                        self.ui.print_show_output(self.output.render(raw, sw_id))
                continue

            # CLI command loop for this step
            attempts = 0
            while not self.sm.can_advance():
                raw = self.ui.prompt(sw_id).strip()
                if not raw:
                    continue

                lower = raw.lower()

                if lower == "quit":
                    self._handle_quit()
                    return

                if lower in ("sw1", "sw2"):
                    self.lab.active_switch = lower.upper()
                    sw_id = self.lab.active_switch
                    self.ui.print_info(f"Switched to {sw_id}")
                    continue

                if lower == "status":
                    self.ui.print_switch_states(self.lab)
                    continue

                if lower == "hint":
                    attempts_so_far = self.guidance.attempts_for(step.number, sw_id)
                    hint = self.guidance.get_hint(step, sw_id, attempts_so_far)
                    tier = 1 if attempts_so_far <= 2 else (2 if attempts_so_far <= 4 else 3)
                    self.ui.print_hint(hint, tier)
                    continue

                if lower == "skip":
                    self._skip_step(step, sw_id)
                    break

                if lower.startswith("show "):
                    self.ui.print_show_output(self.output.render(lower, sw_id))
                    continue

                # Regular config command
                prog = self.sm.step_progress(sw_id)
                next_idx = prog.next_command_index if prog else 0

                result: ValidationResult = self.validator.validate(raw, step, sw_id, next_idx or 0)
                attempts += 1
                self.guidance.record_attempt(step.number, sw_id, result.valid)

                self.ui.print_command_result(result.valid, result.match_type, result.feedback)

                if result.valid:
                    self.sm.mark_command_complete(sw_id, result.command_index)
                    if result.state_updates:
                        self._apply_state_updates(result.state_updates, sw_id, step)

                    # Auto-hint after 3 consecutive failures on a different command
                    attempts = 0

                    # If other switch also needs commands, prompt to switch
                    other = "SW2" if sw_id == "SW1" else "SW1"
                    other_prog = self.sm.get_progress(step.number, other)
                    if (
                        other in step.applies_to
                        and other_prog
                        and not other_prog.complete
                        and (prog and prog.complete)
                    ):
                        self.ui.print_info(
                            f"{sw_id} step complete. Type `{other.lower()}` to switch to {other}."
                        )
                else:
                    if attempts >= 3:
                        auto_hint = self.guidance.get_hint(step, sw_id, attempts)
                        tier = 1 if attempts <= 2 else (2 if attempts <= 4 else 3)
                        self.ui.print_hint(auto_hint, tier)

            self._complete_step(step)

        # Migration complete
        report = self.guidance.report()
        self.ui.print_migration_complete(
            self.guidance.total_score(),
            self.guidance.max_score(),
            report,
        )
        if self.logger:
            path = self.logger.generate_report("session_log_simulator.html")
            self.ui.print_info(f"Session log saved: {path}")

    def _complete_step(self, step: MigrationStep):
        explanation = None
        if self.explain:
            try:
                exp = self.explain.explain(step, "", self.lab.active_switch, self.lab)
                explanation = exp.summary
            except Exception:
                pass
        self.ui.print_step_complete(step, explanation)
        self.ui.console.input("  Press Enter for next step...")
        next_step = self.sm.advance()
        if next_step:
            # Auto-switch to SW1 for next step if it applies to SW1
            if "SW1" in next_step.applies_to:
                self.lab.active_switch = "SW1"

    def _skip_step(self, step: MigrationStep, sw_id: str):
        self.sm.skip_current_step(sw_id)
        self.guidance.record_skip(step.number, sw_id)
        self.ui.print_info(f"Step {step.number} skipped for {sw_id}. -20 points.")

    def _handle_quit(self):
        self.ui.print_info("Saving session...")
        if self.logger:
            path = self.logger.generate_report("session_log_simulator.html")
            self.ui.print_info(f"Session log: {path}")
        self.ui.print_info("Goodbye.")

    def _apply_state_updates(self, updates: dict, switch_id: str, step: MigrationStep):
        """Apply validated command state changes to the SwitchModel."""
        sw: SwitchModel = self.lab.switch(switch_id)

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
            elif key == "nni_isis_enabled":
                sw.nni_isis_enabled = value
            elif key == "nni_no_shutdown":
                sw.nni_no_shutdown = value
            elif key == "pending_ip":
                # apply to last VLAN in context — simplified
                pass
            elif hasattr(sw, key):
                setattr(sw, key, value)

        # Auto-set OS to VOSS when ISIS is configured
        from ..models.switch_state import SwitchOS
        if sw.isis_configured and sw.os == SwitchOS.EXOS:
            sw.os = SwitchOS.VOSS
