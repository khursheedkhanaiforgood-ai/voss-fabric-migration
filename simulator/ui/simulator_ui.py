"""
SimulatorUI — Rich terminal interface for the EXOS→VOSS Digital Twin Simulator.

Layout:
  ┌─────────────────────────────────────────────────────────────┐
  │  Header: step progress bar + score + phase label            │
  ├───────────────────────┬─────────────────────────────────────┤
  │  SW1 state panel      │  SW2 state panel                    │
  ├───────────────────────┴─────────────────────────────────────┤
  │  Current step description + standard reference              │
  │  EXOS→VOSS learning note (links back to source project)     │
  ├─────────────────────────────────────────────────────────────┤
  │  [SW1]# or [SW2]# — student input prompt                   │
  └─────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn
from rich.rule import Rule

from .themes import SIMULATOR_THEME, STEP_STATUS_ICON, SWITCH_COLOR
from ..models.lab_state import LabState
from ..models.migration_step import MigrationStep, MIGRATION_STEPS
from ..services.state_machine_service import StateMachineService
from ..services.student_guidance import StudentGuidanceService
from ..config import EXOS_LAB, STANDARDS


class SimulatorUI:

    def __init__(self):
        self.console = Console(theme=SIMULATOR_THEME, highlight=False)

    def print_welcome(self):
        self.console.print()
        self.console.print(Rule("[bold white]EXOS / SwitchEngine  →  VOSS / FabricEngine[/bold white]", style="cyan"))
        self.console.print(
            Panel(
                "[bold white]Digital Twin Simulator[/bold white]\n"
                "[dim]Extreme Networks 5320 Lab — 2 Switches · 2 AP3000s · 4 SSIDs[/dim]\n\n"
                "[step.completed]Prerequisite:[/step.completed] "
                f"[link={EXOS_LAB['landing_page']}]{EXOS_LAB['title']}[/link]  "
                f"[dim](completed EXOS deployment — same hardware, same XIQ org)[/dim]\n"
                f"[dim]  Lab Guide: {EXOS_LAB['lab_guide']}[/dim]\n"
                f"[dim]  Apr 8 E2E: {EXOS_LAB['apr8_session']}[/dim]",
                title="[bold cyan]Welcome[/bold cyan]",
                border_style="cyan",
            )
        )
        self._print_topology()
        self._print_standards_reference()
        self.console.print()

    def _print_topology(self):
        self.console.print(
            Panel(
                "  [switch.sw1]SW1[/switch.sw1] (5320-16P)               [switch.sw2]SW2[/switch.sw2] (5320-16P)\n"
                "   Port 1: Modem ←→ 192.168.1.1      Port 1: Modem ←→ 192.168.1.1\n"
                "   Port 3: AP3000 (FA client)         Port 3: AP3000 (FA client)\n"
                "   Port17: ══════════ NNI ═══════════ Port 17\n"
                "           IS-IS/SPB IEEE 802.1aq\n\n"
                "  VLANs/I-SIDs: 10=MGMT·100010  20=Alpha·100020  30=Bravo·100030\n"
                "                50=Delta·100050  60=Gamma·100060",
                title="[dim]Lab Topology[/dim]",
                border_style="dim",
            )
        )

    def _print_standards_reference(self):
        t = Table(title="Governing Standards — Fabric Connect Deployment", show_lines=True)
        t.add_column("Standard", style="standard.ref", no_wrap=True)
        t.add_column("Title", style="white")
        t.add_column("Relevance to This Lab", style="dim white")
        for s in STANDARDS:
            t.add_row(s["id"], s["title"], s["relevance"])
        self.console.print(t)

    def print_step_header(
        self,
        step: MigrationStep,
        sm: StateMachineService,
        score: int,
        active_switch: str,
    ):
        self.console.print()
        self.console.print(Rule(style="dim"))
        pct = int(sm.overall_progress() * 100)
        header = (
            f"[step.active]Step {step.number}/{sm.total_steps}[/step.active]  "
            f"[phase.label] {step.phase.value} [/phase.label]  "
            f"Progress: [bold green]{pct}%[/bold green]  "
            f"Score: [bold yellow]{score}[/bold yellow]"
        )
        self.console.print(header)
        self.console.print(f"[bold white]{step.name}[/bold white]")
        self.console.print()
        self.console.print(
            Panel(
                f"{step.description}\n\n"
                f"[exos.ref]EXOS parallel:[/exos.ref] {step.exos_parallel}\n\n"
                f"[standard.ref]Standard:[/standard.ref] {step.standard}",
                title=f"[step.active]Step {step.number}: {step.name}[/step.active]",
                border_style="cyan",
            )
        )

    def print_switch_states(self, lab: LabState):
        sw1_table = self._make_state_table(lab.sw1)
        sw2_table = self._make_state_table(lab.sw2)
        self.console.print(Panel(sw1_table, title="[switch.sw1]SW1 — 0000.0000.0001[/switch.sw1]", border_style="blue"))
        self.console.print(Panel(sw2_table, title="[switch.sw2]SW2 — 0000.0000.0002[/switch.sw2]", border_style="magenta"))
        health = lab.health_summary()
        adj = "[status.up]UP[/status.up]" if health["ISIS adjacency"] == "UP" else "[status.down]DOWN[/status.down]"
        self.console.print(f"  ISIS adjacency: {adj}  |  Fabric services: {health['Fabric services visible']}  |  E2E: {health['E2E connectivity']}")
        if health["Adjacency failure reason"] != "n/a":
            self.console.print(f"  [status.down]Fault: {health['Adjacency failure reason']}[/status.down]")

    def _make_state_table(self, sw) -> Table:
        t = Table(show_header=False, box=None, padding=(0, 1))
        t.add_column("Key", style="dim")
        t.add_column("Value", style="white")
        for k, v in sw.summary_dict().items():
            t.add_row(k, str(v))
        return t

    def print_command_result(self, valid: bool, match_type: str, feedback: str):
        if valid:
            icon = "[command.valid]✓[/command.valid]"
            style = "command.valid"
        elif match_type == "partial":
            icon = "[command.partial]~[/command.partial]"
            style = "command.partial"
        else:
            icon = "[command.invalid]✗[/command.invalid]"
            style = "command.invalid"
        self.console.print(f"  {icon} [{style}]{feedback}[/{style}]")

    def print_show_output(self, output: str):
        self.console.print(
            Panel(
                Text(output, style="white"),
                border_style="dim",
                title="[dim]show command output[/dim]",
            )
        )

    def print_hint(self, hint: str, tier: int):
        tier_styles = {1: "hint.tier1", 2: "hint.tier2", 3: "hint.tier3"}
        style = tier_styles.get(tier, "hint.tier1")
        self.console.print(
            Panel(
                f"[{style}]{hint}[/{style}]",
                title=f"[dim]Hint (tier {tier})[/dim]",
                border_style="yellow",
            )
        )

    def print_step_complete(self, step: MigrationStep, explanation: str | None = None):
        self.console.print()
        self.console.print(Rule("[step.completed]Step Complete[/step.completed]", style="green"))
        self.console.print(f"  [step.completed]✓ Step {step.number}: {step.name}[/step.completed]")
        if explanation:
            self.console.print(
                Panel(
                    explanation,
                    title="[dim]What just happened[/dim]",
                    border_style="green",
                )
            )

    def print_migration_complete(self, score: int, max_score: int, report: dict):
        self.console.print()
        self.console.print(Rule("[bold green]Migration Complete![/bold green]", style="green"))
        self.console.print(
            Panel(
                f"[bold green]All 18 steps complete.[/bold green]\n\n"
                f"Score: [bold yellow]{score}[/bold yellow] / {max_score}\n\n"
                "Your lab now matches the VOSS/FabricEngine target state:\n"
                "  - IS-IS adjacency: UP (L1L2)\n"
                "  - 5 I-SIDs active across the fabric\n"
                "  - 4 SSIDs served via Fabric Attach\n"
                "  - Internet via anycast Quantum Fiber exit\n\n"
                f"[dim]Compare with your EXOS baseline:\n{EXOS_LAB['apr8_session']}[/dim]",
                title="[bold green]Congratulations[/bold green]",
                border_style="green",
            )
        )

    def prompt(self, active_switch: str) -> str:
        """Display switch prompt and return student input."""
        color = SWITCH_COLOR.get(active_switch, "white")
        self.console.print(f"  [dim]Type a VOSS command, `show <cmd>`, `hint`, `skip`, `sw1`/`sw2`, or `quit`[/dim]")
        return self.console.input(f"  [{color}][{active_switch}]#[/{color}] ")

    def print_error(self, message: str):
        self.console.print(f"  [bold red]Error:[/bold red] {message}")

    def print_info(self, message: str):
        self.console.print(f"  [dim]{message}[/dim]")
