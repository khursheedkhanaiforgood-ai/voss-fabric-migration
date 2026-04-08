"""
StateMachineService — tracks migration progress across the 18 steps.

Enforces step ordering, tracks per-switch command completion,
and determines when the student can advance to the next step.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from ..models.migration_step import MigrationStep, MIGRATION_STEPS, get_step


@dataclass
class StepProgress:
    """Tracks completion of commands within one step for one switch."""
    switch_id: str
    step_number: int
    total_commands: int
    completed_indices: set[int] = field(default_factory=set)
    skipped: bool = False
    confirmed: bool = False  # for narrative/destructive steps

    @property
    def complete(self) -> bool:
        if self.skipped:
            return True
        if self.total_commands == 0:
            return self.confirmed
        return len(self.completed_indices) >= self.total_commands

    @property
    def next_command_index(self) -> int | None:
        for i in range(self.total_commands):
            if i not in self.completed_indices:
                return i
        return None


class StateMachineService:
    """
    Tracks which of the 18 migration steps is active and whether it's complete.

    Design principles:
    - Steps must be completed in order (prerequisites enforced)
    - Each step may apply to SW1 only, SW2 only, or both
    - Narrative steps (is_narrative=True) require a confirmation, not CLI commands
    - A step is complete when all required switches have entered all required commands
    """

    def __init__(self):
        self._current_step_number: int = 1
        self._progress: dict[tuple[int, str], StepProgress] = {}
        self._initialize_progress()

    def _initialize_progress(self):
        """Pre-build StepProgress objects for all 18 steps × applicable switches."""
        for step in MIGRATION_STEPS:
            for switch_id in step.applies_to:
                cmds = step.expected_commands.get(switch_id, [])
                key = (step.number, switch_id)
                self._progress[key] = StepProgress(
                    switch_id=switch_id,
                    step_number=step.number,
                    total_commands=len(cmds),
                )

    # ── Read-only properties ──────────────────────────────────────────────────

    @property
    def current_step(self) -> MigrationStep:
        return get_step(self._current_step_number)

    @property
    def current_step_number(self) -> int:
        return self._current_step_number

    @property
    def total_steps(self) -> int:
        return len(MIGRATION_STEPS)

    def overall_progress(self) -> float:
        """Fraction of steps fully completed (0.0 to 1.0)."""
        completed = sum(
            1 for n in range(1, self._current_step_number)
        )
        return completed / self.total_steps

    def step_progress(self, switch_id: str) -> StepProgress | None:
        return self._progress.get((self._current_step_number, switch_id))

    def get_progress(self, step_number: int, switch_id: str) -> StepProgress | None:
        return self._progress.get((step_number, switch_id))

    # ── Mutation ──────────────────────────────────────────────────────────────

    def mark_command_complete(self, switch_id: str, command_index: int) -> None:
        prog = self._progress.get((self._current_step_number, switch_id))
        if prog:
            prog.completed_indices.add(command_index)

    def mark_confirmed(self, switch_id: str) -> None:
        """For narrative steps — student pressed Enter to confirm."""
        prog = self._progress.get((self._current_step_number, switch_id))
        if prog:
            prog.confirmed = True

    def skip_current_step(self, switch_id: str) -> None:
        prog = self._progress.get((self._current_step_number, switch_id))
        if prog:
            prog.skipped = True

    def can_advance(self) -> bool:
        """True when all required switches have completed the current step."""
        step = self.current_step
        for switch_id in step.applies_to:
            prog = self._progress.get((step.number, switch_id))
            if prog is None or not prog.complete:
                return False
        return True

    def advance(self) -> MigrationStep | None:
        """
        Move to the next step. Returns the new step, or None if migration complete.
        Raises RuntimeError if prerequisites are not met.
        """
        if not self.can_advance():
            raise RuntimeError(
                f"Cannot advance: step {self._current_step_number} "
                f"({self.current_step.name}) is not complete on all required switches."
            )
        if self._current_step_number >= self.total_steps:
            return None
        self._current_step_number += 1
        return self.current_step

    def is_complete(self) -> bool:
        """True when all 18 steps are done."""
        return self._current_step_number > self.total_steps

    # ── Status helpers ────────────────────────────────────────────────────────

    def step_status(self, step_number: int) -> str:
        """Return 'completed', 'active', or 'pending'."""
        if step_number < self._current_step_number:
            return "completed"
        if step_number == self._current_step_number:
            return "active"
        return "pending"

    def status_table(self) -> list[dict]:
        """Full status table for UI display."""
        rows = []
        for step in MIGRATION_STEPS:
            status = self.step_status(step.number)
            switch_status = {}
            for sw in step.applies_to:
                prog = self._progress.get((step.number, sw))
                if prog:
                    if prog.complete:
                        sw_label = "done"
                    elif step.is_narrative:
                        sw_label = "confirm"
                    elif prog.total_commands > 0:
                        done = len(prog.completed_indices)
                        sw_label = f"{done}/{prog.total_commands}"
                    else:
                        sw_label = "pending"
                    switch_status[sw] = sw_label
            rows.append({
                "number": step.number,
                "name": step.name,
                "phase": step.phase.value,
                "status": status,
                "switches": switch_status,
            })
        return rows
