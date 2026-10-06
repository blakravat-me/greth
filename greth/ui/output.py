"""Scrolling output printed into the scrollback: plans, observations, tool calls, and results."""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text

from .console import console

"""Styled-line composer shared by live and dynamic output: prefix + symbol + text."""


def compose_line(
    text: str,
    symbol: str,
    symbol_style: str,
    text_style: str,
    *,
    prefix: str = "",
    no_wrap: bool = False,
) -> Text:
    """Build one 'prefix + styled symbol + styled text' Rich Text line."""
    line = Text(no_wrap=no_wrap, overflow="ellipsis" if no_wrap else "fold")

    if prefix:
        line.append(prefix)

    line.append(symbol, style=symbol_style)
    line.append(f" {text}", style=text_style)

    return line


def _print(text: object, symbol: str, symbol_style: str, text_style: str, padding: str = "") -> None:
    """Print one composed line, then an unconditional blank separator line."""
    text = str(text).strip()

    if text:
        line = compose_line(text, symbol, symbol_style, text_style, prefix=padding)
        line.append(padding)
        console.print(line)

    console.print()  # separator is unconditional: always exactly one blank line


def out_message(text: object) -> None:
    """Print an observation line."""
    _print(text, symbol="●", symbol_style="blue", text_style="white", padding="  ")


def out_tool_result(name: str, reference: str, output: str, *, failed: bool = False) -> None:
    """Display a complete tool result with its artifact reference and status."""
    console.print(
        Panel(
            Text(output or "[No output.]"),
            title=f"{'Tool error' if failed else 'Tool result'}: {name}",
            subtitle=f"Artifact: {reference}",
            border_style="red" if failed else "cyan",
        )
    )


def out_error(message: str) -> None:
    """Display an actionable error in the shared terminal UI."""
    console.print(f"[bold red]Stopped due to an error:[/bold red] {message}")


def out_terminal(username: str, hostname: str, cwd: str, command: str) -> None:
    """Print a fake terminal prompt box showing the command about to run."""
    prompt = Text()
    prompt.append("  ┌──(", style="blue")
    prompt.append(username, style="red")
    prompt.append("㉿", style="red")
    prompt.append(hostname, style="red")
    prompt.append(")-[", style="blue")
    prompt.append(cwd, style="white")
    prompt.append("]", style="blue")
    prompt.append("\n")
    prompt.append("  └─", style="blue")
    prompt.append("#", style="red")
    prompt.append(f" {str(command).strip()}", style="white")
    console.print(prompt)
