"""
needoh/ui/display.py
Rich terminal rendering for Needoh.
Handles the banner, tool call panels, streaming output, and spinners.
"""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.live import Live
from rich.spinner import Spinner
from rich.columns import Columns
from rich import box
import json

console = Console()

# ── Colour palette ───────────────────────────────────────────────────────────
ACCENT   = "bright_yellow"   # Needoh brand colour
DIM      = "grey62"
SUCCESS  = "bright_green"
ERROR    = "bright_red"
INFO     = "bright_cyan"
TOOL     = "bright_magenta"
RESULT   = "grey70"


def print_banner() -> None:
    """Print the Needoh startup banner."""
    banner = Text()
    banner.append("\n")
    banner.append("  ███╗   ██╗███████╗███████╗██████╗  ██████╗ ██╗  ██╗\n", style=ACCENT)
    banner.append("  ████╗  ██║██╔════╝██╔════╝██╔══██╗██╔═══██╗██║  ██║\n", style=ACCENT)
    banner.append("  ██╔██╗ ██║█████╗  █████╗  ██║  ██║██║   ██║███████║\n", style=ACCENT)
    banner.append("  ██║╚██╗██║██╔══╝  ██╔══╝  ██║  ██║██║   ██║██╔══██║\n", style=ACCENT)
    banner.append("  ██║ ╚████║███████╗███████╗██████╔╝╚██████╔╝██║  ██║\n", style=ACCENT)
    banner.append("  ╚═╝  ╚═══╝╚══════╝╚══════╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝\n", style=ACCENT)
    banner.append("  Autonomous CLI Coding Assistant  ", style=DIM)
    banner.append("v0.1.0\n", style=DIM)
    console.print(banner)


def print_provider_info(provider: str, model: str, auto: bool) -> None:
    """Print current provider and mode info after banner."""
    mode = "[bright_red]AUTO[/]" if auto else "[bright_green]CONFIRM[/]"
    console.print(
        f"  Provider [bold]{provider.upper()}[/] · Model [bold]{model}[/] · Mode {mode}\n",
        style=DIM,
    )


def print_help() -> None:
    """Print the slash command help table."""
    console.print(Panel(
        "[bold]Slash commands[/]\n\n"
        f"  [bold {ACCENT}]/help[/]               Show this message\n"
        f"  [bold {ACCENT}]/provider groq|ollama[/] Switch LLM provider\n"
        f"  [bold {ACCENT}]/model <name>[/]         Set model name\n"
        f"  [bold {ACCENT}]/auto[/]                Toggle auto-execute mode\n"
        f"  [bold {ACCENT}]/clear[/]               Clear conversation history\n"
        f"  [bold {ACCENT}]/exit[/]                Quit Needoh",
        title="[bold]Needoh Help[/]",
        border_style=ACCENT,
        box=box.ROUNDED,
    ))


def print_tool_call(tool_name: str, args: dict) -> None:
    """Display a tool invocation panel so the user knows what Needoh is doing."""
    # Pretty-print the arguments as JSON syntax
    args_str = json.dumps(args, indent=2)
    syntax = Syntax(args_str, "json", theme="monokai", background_color="default")

    console.print(Panel(
        syntax,
        title=f"[bold {TOOL}]⚙  tool call → {tool_name}[/]",
        border_style=TOOL,
        box=box.ROUNDED,
        padding=(0, 1),
    ))


def print_tool_result(result: str, tool_name: str = "") -> None:
    """Display the result returned by a tool (dimmed)."""
    # Truncate very long results for display
    display = result if len(result) < 1200 else result[:1200] + "\n… (truncated)"
    console.print(Panel(
        f"[{RESULT}]{display}[/]",
        title=f"[{DIM}]result ← {tool_name}[/]" if tool_name else f"[{DIM}]result[/]",
        border_style=DIM,
        box=box.ROUNDED,
        padding=(0, 1),
    ))


def print_confirm_prompt(tool_name: str, args: dict) -> bool:
    """
    Ask the user whether to execute a tool call.
    Returns True if approved, False if skipped.
    """
    print_tool_call(tool_name, args)
    console.print(f"  [{ACCENT}]Execute this tool? [y/N][/] ", end="")
    answer = input().strip().lower()
    return answer in ("y", "yes")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"\n[{ERROR}]✗ {message}[/]\n")


def print_info(message: str) -> None:
    """Print an informational message."""
    console.print(f"[{INFO}]ℹ  {message}[/]")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[{SUCCESS}]✓ {message}[/]")


def print_mode_toggle(auto: bool) -> None:
    """Announce auto-execute mode toggle."""
    if auto:
        console.print(f"[{ERROR}]⚡ Auto-execute ON — Needoh will run tools without asking.[/]")
    else:
        console.print(f"[{SUCCESS}]🔒 Confirm mode ON — Needoh will ask before running tools.[/]")


def stream_llm_response(token: str) -> None:
    """
    Print a single streaming token. Called repeatedly as tokens arrive.
    Caller is responsible for printing a newline when streaming ends.
    """
    console.print(token, end="", markup=False)


def end_stream() -> None:
    """Print a newline after streaming finishes."""
    console.print()


class SpinnerContext:
    """
    Context manager that shows a spinner with a status message.

    Usage:
        with SpinnerContext("Thinking..."):
            result = do_slow_thing()
    """
    def __init__(self, message: str):
        self.message = message
        self._live = Live(
            Spinner("dots", text=f"[{DIM}]{message}[/]"),
            console=console,
            refresh_per_second=12,
            transient=True,
        )

    def __enter__(self):
        self._live.__enter__()
        return self

    def __exit__(self, *args):
        self._live.__exit__(*args)
