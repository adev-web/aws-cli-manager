import os
import re
import subprocess
import sys
from pathlib import Path

import typer

from .logger import console, info, success, warn, raw, die
from .config import Config
from .aws.session import app as aws_app
from .db.tunnel import app as db_app
from .ssm.tunnel import CLUSTER_ALIASES, app as ssm_app
from .kafka.manager import app as kafka_app
from .workflow.debug import app as workflow_app
from .verbs.run import run_app
from .verbs.stop import stop_app
from .verbs.login import login_app
from .verbs.exec import exec_app
from .verbs.logs import logs_app


def _win_to_posix(path: str) -> str:
    p = path.replace("\\", "/")
    if sys.platform == "win32" and re.match(r"^[A-Za-z]:/", p):
        p = f"/{p[0].lower()}{p[2:]}"
    return p

app = typer.Typer(
    name="yappy",
    help="AWS CLI Manager - orchestrate AWS, DB, Kafka, and SSM workflows",
    no_args_is_help=True,
)

# Viejos (deprecated)
app.add_typer(aws_app, name="aws", help="AWS session management [deprecated]")
app.add_typer(db_app, name="db", help="Database tunnel management [deprecated]")
app.add_typer(ssm_app, name="ssm", help="SSM tunnels [deprecated]")
app.add_typer(kafka_app, name="kafka", help="Local Kafka [deprecated]")
app.add_typer(workflow_app, name="workflow", help="Workflows [deprecated]")

# Nuevos (Docker-like)
app.add_typer(run_app, name="run", help="Start a resource")
app.add_typer(stop_app, name="stop", help="Stop a resource")
app.add_typer(login_app, name="login", help="Authenticate with AWS")
app.add_typer(exec_app, name="exec", help="Execute commands in environment context")
app.add_typer(logs_app, name="logs", help="Show logs of managed processes")


@app.command()
def version():
    """Show the installed version."""
    from importlib.metadata import version as _v
    try:
        ver = _v("aws-cli-manager")
    except Exception:
        ver = "0.1.0 (dev)"
    info(f"aws-cli-manager v{ver}")


@app.command()
def config(env: str = typer.Argument(None, help="Environment to show (dev, qa, ...)")):
    """Show configuration for one or all environments."""
    known = Config.known_environments()
    envs = [env] if env else known

    for e in envs:
        try:
            cfg = Config.with_env(e)
        except ValueError:
            info(f"No config found for '{e}'")
            continue
        if env and len(envs) > 1:
            print()
        info(f"[bold]=== {e.upper()} ===[/bold]")
        info(f"  AWS Profile:  {cfg.profile}")
        info(f"  AWS Region:   {cfg.region}")
        info(f"  AWS Instance: {cfg.instance or '(not set)'}")
        info(f"  AWS Host:     {cfg.host or '(not set)'}")
        info(f"  AWS Cluster:  {cfg.cluster or '(not set)'}")
        info(f"  DB Port:      {cfg.db_port}")

    if not env:
        base = Config()
        print()
        info("[bold]=== BASE ===[/bold]")
        info(f"  AWS User:     {base.aws_user}")
        info(f"  Kafka Path:   {base.kafka_path}")
        info(f"  Profile:      {base.profile_path}")
        info(f"  Workspace:    {base.workspace_path}")


@app.command()
def workspace():
    """Show the project workspace path."""
    cfg = Config()
    print(_win_to_posix(cfg.workspace_path))


@app.command()
def home():
    """Show the yappy project root path."""
    print(_win_to_posix(str(Path(__file__).resolve().parent.parent)))


@app.command()
def init(shell: str = typer.Argument("bash", help="Shell type: bash, zsh, powershell")):
    """Generate shell integration — add to .bashrc: eval "$(yappy init bash)"."""
    if shell == "powershell":
        print(r"""function yappy {
  if ($args[0] -eq "workspace") { Set-Location (yappy workspace) }
  elseif ($args[0] -eq "home") { Set-Location (yappy home) }
  elseif ($args[0] -eq "reload") { yappy reload; . $PROFILE }
  else { yappy @args }
}""")
        return

    print(r"""# yappy shell integration
yappy() {
  if [ "$1" = "workspace" ]; then
    cd "$(command yappy workspace)"
  elif [ "$1" = "home" ]; then
    cd "$(command yappy home)"
  elif [ "$1" = "reload" ]; then
    command yappy reload && source ~/.bashrc
  else
    command yappy "$@"
  fi
}""")


@app.command()
def reload():
    """Reinstall the package in editable mode (pip install -e .)."""
    project_root = Path(__file__).resolve().parent.parent
    pyproject = project_root / "pyproject.toml"
    version_str = "unknown"
    if pyproject.exists():
        for line in pyproject.read_text().splitlines():
            if line.strip().startswith('version'):
                version_str = line.split("=")[1].strip().strip('"').strip("'")
                break
    info(f"Reinstalling Yappy-ToolKit v{version_str} from {project_root}...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(project_root)],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        success(f"Yappy-ToolKit v{version_str} reinstalled successfully")
    else:
        die(f"Reinstall failed: {result.stderr.strip()}")


def _parse_ssm_info(cmdline: str) -> tuple[str, str]:
    env = os.environ.get("AWS_ENVIRONMENT") or ""
    if not env:
        prof_m = re.search(r'--profile\s+(\S+)', cmdline)
        env = prof_m.group(1).split("-")[-1] if prof_m else "?"

    if "AWS-StartPortForwardingSessionToRemoteHost" not in cmdline:
        return "Bastion", env

    host_m = re.search(r'"host":\["([^"]+)"\]', cmdline)
    if not host_m:
        return "Port Forward", env
    host = host_m.group(1)

    host_parts = host.split(".")
    if len(host_parts) >= 3:
        env = host_parts[1]

    for alias, prefix in sorted(CLUSTER_ALIASES.items(), key=lambda x: -len(x[1])):
        if host.startswith(prefix + "."):
            return f"SSM Tunnel - {alias}", env

    if "rds" in host:
        return "DB Tunnel", env

    return f"SSM Tunnel - {host_parts[0]}", env


@app.command()
def ps():
    """List active processes started by Yappy-ToolKit."""
    from rich.table import Table
    from rich import box

    rows = []
    known_pids = set()
    port_map = {}

    try:
        netstat = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10,
        )
        for line in netstat.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and parts[0] == "TCP" and "127.0.0.1:" in parts[1]:
                port = parts[1].split(":")[1]
                pid = parts[-1]
                port_map.setdefault(pid, []).append(port)
    except Exception:
        pass

    # AWS CLI processes running SSM sessions (has full command line with target info)
    try:
        ps_cmd = [
            "powershell", "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='aws.exe' AND CommandLine LIKE '%ssm start-session%'\""
            " | ForEach-Object { $_.ProcessId.ToString() + '|' + $_.CommandLine }",
        ]
        result = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=10)
        for line in result.stdout.strip().splitlines():
            if "|" not in line:
                continue
            pid, cmdline = line.split("|", 1)
            pid = pid.strip()
            if not pid.isdigit() or pid in known_pids:
                continue
            known_pids.add(pid)
            label, env = _parse_ssm_info(cmdline)
            for p in (port_map.get(pid, ["?"])):
                rows.append((pid, env, label, p))
    except Exception:
        pass

    # session-manager-plugin.exe (orphan tunnels where CLI already exited)
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq session-manager-plugin.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.strip('"').split('","')
            if len(parts) < 2:
                continue
            pid = parts[1].strip()
            if pid in known_pids:
                continue
            known_pids.add(pid)
            for p in (port_map.get(pid, ["?"])):
                rows.append((pid, "?", "SSM Plugin", p))
    except Exception:
        pass

    # Java processes: Kafka server + Kafdrop UI
    try:
        result = subprocess.run(["jps", "-l"], capture_output=True, text=True, timeout=10)
        for line in result.stdout.strip().splitlines():
            parts = line.strip().split()
            if len(parts) == 2:
                pid, name = parts
                if pid in known_pids:
                    continue
                known_pids.add(pid)
                if "kafka.Kafka" in name:
                    rows.append((pid, "-", "Kafka Server", "9092"))
                elif "main.jar" in name:
                    rows.append((pid, "-", "Kafdrop UI", "8080"))
    except FileNotFoundError:
        pass
    except Exception:
        pass

    if not rows:
        info("No active Yappy-ToolKit processes found.")
        return

    table = Table(box=box.SIMPLE)
    table.add_column("PID", style="cyan")
    table.add_column("Env")
    table.add_column("Type")
    table.add_column("Port", style="yellow")

    for pid, env, kind, port in rows:
        table.add_row(pid, env, kind, port)

    console.print(table)


@app.command()
def edit():
    """Open the yappy project in VS Code."""
    project_root = Path(__file__).resolve().parent.parent
    info(f"Opening {project_root} in VS Code...")
    subprocess.run(["code", str(project_root)])


@app.command(name="py-purge")
def py_purge():
    """Clear pip cache."""
    info("Clearing pip cache...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "cache", "purge"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        success("Pip cache purged")
    else:
        die(f"Failed to purge pip cache: {result.stderr.strip()}")


def _replace_wrapper_with_eval(bashrc: Path):
    content = bashrc.read_text()
    lines = content.splitlines()
    cleaned = []
    skip = False
    for line in lines:
        if line.strip() == "yappy() {":
            skip = True
        if not skip:
            cleaned.append(line)
        if skip and line.strip() == "}":
            skip = False
    cleaned.append('')
    cleaned.append('eval "$(yappy init bash)"')
    bashrc.write_text("\n".join(cleaned) + "\n")


def _setup_config(config_dir: Path):
    examples = sorted(config_dir.glob("*.example"))
    for example in examples:
        target_name = example.name.replace(".example", "")
        # skip generic template pattern
        if target_name == "env.environment":
            continue
        target = config_dir / target_name
        if target.exists():
            success(f"  {target_name} already exists")
        else:
            warn(f"  {target_name} not found")
            yn = input(f"  Create from {example.name}? (Y/n): ")
            if yn.lower() != "n":
                content = example.read_text()
                target.write_text(content)
                success(f"  Created {target_name} — edit values before using")
                info(f"    → yappy edit")


@app.command()
def setup():
    """One-time project setup: shell integration, config, dependencies."""
    project_root = Path(__file__).resolve().parent.parent
    config_dir = project_root / "config"

    info("=== Yappy Setup ===")
    print()

    # 1. Shell integration
    bashrc = Path.home() / ".bashrc"
    eval_marker = 'eval "$(yappy init bash)"'
    has_eval = bashrc.exists() and eval_marker in bashrc.read_text()
    has_wrapper = bashrc.exists() and "yappy() {" in bashrc.read_text()

    if has_eval:
        success("Shell integration already in .bashrc")
    elif has_wrapper:
        info("Found manual yappy() wrapper — replace with eval line?")
        yn = input("  Auto-replace? (Y/n): ")
        if yn.lower() != "n":
            _replace_wrapper_with_eval(bashrc)
            success("Replaced wrapper with eval integration")
        else:
            info("  Skipped")
    elif bashrc.exists():
        with open(bashrc, "a") as f:
            f.write(f"\n{eval_marker}\n")
        success(f"Added shell integration to {bashrc}")
    else:
        warn(f"No .bashrc found at {bashrc}")
        info(f"  Add manually:\n  {eval_marker}")

    # 2. Config files
    print()
    info("Config files:")
    _setup_config(config_dir)

    # 3. Dependencies
    print()
    info("Dependencies:")
    for cmd_name in ("aws", "session-manager-plugin"):
        result = subprocess.run(
            ["where", cmd_name] if sys.platform == "win32" else ["which", cmd_name],
            capture_output=True, shell=True,
        )
        if result.returncode == 0:
            success(f"  {cmd_name} found")
        else:
            warn(f"  {cmd_name} not found — install it first")

    # 4. AWS profile
    print()
    info("AWS profile:")
    cfg = Config()
    result = subprocess.run(
        ["aws", "configure", "list", "--profile", cfg.profile],
        capture_output=True, text=True, shell=True,
    )
    if result.returncode == 0:
        success(f"  Profile '{cfg.profile}' configured")
    else:
        warn(f"  Profile '{cfg.profile}' not found — configure it with 'aws configure'")

    print()
    success("Setup complete. Run 'source ~/.bashrc' to load changes.")


if __name__ == "__main__":
    app()
