"""Color and style definitions for the simulator Rich terminal UI."""

from rich.style import Style
from rich.theme import Theme

SIMULATOR_THEME = Theme({
    "step.active":     "bold cyan",
    "step.completed":  "green",
    "step.pending":    "dim white",
    "step.skipped":    "yellow",
    "status.up":       "bold green",
    "status.down":     "bold red",
    "status.pending":  "yellow",
    "standard.ref":    "dim cyan",
    "exos.ref":        "dim magenta",
    "hint.tier1":      "yellow",
    "hint.tier2":      "bold yellow",
    "hint.tier3":      "bold red",
    "command.valid":   "bold green",
    "command.invalid": "bold red",
    "command.partial": "yellow",
    "switch.sw1":      "bold blue",
    "switch.sw2":      "bold magenta",
    "phase.label":     "bold white on dark_blue",
    "nyt.blue":        "#326891",
})

STEP_STATUS_ICON = {
    "completed": "[green]✓[/green]",
    "active":    "[bold cyan]▶[/bold cyan]",
    "pending":   "[dim]○[/dim]",
    "skipped":   "[yellow]⊘[/yellow]",
}

SWITCH_COLOR = {
    "SW1": "blue",
    "SW2": "magenta",
}
