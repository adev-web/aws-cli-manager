from __future__ import annotations

from pathlib import Path

import typer

from ..logger import info, warn, console

logs_app = typer.Typer(help="Show logs of managed processes")


@logs_app.command(name="db")
def logs_db(
    env: str = typer.Argument(..., help="Environment: dev, qa, ..."),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
):
    """Show logs for DB tunnel."""
    _show_logs("db", env, follow, lines)


@logs_app.command(name="kafka")
def logs_kafka(
    target: str = typer.Argument(..., help="server or ui"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
):
    """Show logs for Kafka server or UI."""
    _show_logs("kafka", target, follow, lines)


@logs_app.command(name="tunnel")
def logs_tunnel(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
):
    """Show logs for SSM tunnels."""
    _show_logs("tunnel", "", follow, lines)


def _show_logs(resource: str, target: str, follow: bool, lines: int):
    from ..process_tracker import get_tracked_processes
    processes = get_tracked_processes(resource=resource, target=target)

    if not processes:
        info(f"No tracked processes found for '{resource}'.")
        info("Processes are tracked automatically when started with yappy run/stop.")
        return

    for proc in processes:
        log_file = proc.get("log_file", "")
        pid = proc.get("pid", "?")
        alive = proc.get("alive", False)
        status = "alive" if alive else "dead"
        info(f"Process {pid} ({resource}/{target}) — {status}")

        if log_file and Path(log_file).exists():
            content = Path(log_file).read_text(encoding="utf-8", errors="replace")
            log_lines = content.splitlines()
            show = log_lines[-lines:] if len(log_lines) > lines else log_lines
            for line in show:
                console.print(line)
        else:
            info(f"  No log file available for PID {pid}.")
