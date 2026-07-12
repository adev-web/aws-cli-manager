from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import botocore.session
import typer

from ..base import BaseCommand
from ..config import Config
from ..deprecation import warn_deprecated
from ..logger import success, info, warn, die

app = typer.Typer(help="Database tunnel management")
REFRESH_INTERVAL = 12 * 60  # 12 minutes (token expires in 15)


class DbCommand(BaseCommand):
    pass


db_cmd = DbCommand()


def _generate_token(cfg: Config) -> str:
    # Try botocore first
    try:
        bc_session = botocore.session.Session(profile=cfg.profile)
        rds = bc_session.create_client("rds", region_name=cfg.require("AWS_REGION"))
        token = rds.generate_db_auth_token(
            DBHostname=cfg.require("AWS_HOST"),
            Port=int(cfg.get("AWS_PORT", "53360")),
            DBUsername=cfg.require("AWS_USER"),
            Region=cfg.require("AWS_REGION"),
        )
        if token:
            return token
    except Exception as e:
        warn(f"botocore token failed, trying fallback: {e}")

    # Fallback: python -m awscli
    cmd = [
        sys.executable, "-m", "awscli", "rds", "generate-db-auth-token",
        "--hostname", cfg.require("AWS_HOST"),
        "--port", cfg.get("AWS_PORT", "53360"),
        "--username", cfg.require("AWS_USER"),
        "--region", cfg.require("AWS_REGION"),
        "--profile", cfg.profile,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        die(f"Failed to generate DB token: {result.stderr.strip()}")
    return result.stdout.strip()


def _clipboard(text: str):
    try:
        if sys.platform == "win32":
            subprocess.run(["clip"], input=text, text=True, check=False)
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text, text=True, check=False)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True, check=False)
    except Exception:
        pass


def _write_local_env(token: str):
    env_local = Path(__file__).resolve().parent.parent.parent / "config" / ".env.local"

    try:
        existing = {}
        if env_local.exists():
            for line in env_local.read_text().splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    existing[k] = v
        existing["DB_PASSWORD"] = token
        if "DB_USER" not in existing:
            existing["DB_USER"] = Config().aws_user or ""
        content = "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n"
        env_local.write_text(content)
        success(f"Token saved to {env_local}")
    except Exception as e:
        warn(f"Could not write {env_local}: {e}")

    _clipboard(token)
    success("Token copied to clipboard")


def _start_refresher(cfg: Config, stop_event: threading.Event):
    def refresher():
        while not stop_event.wait(REFRESH_INTERVAL):
            info("Refreshing DB token...")
            try:
                new_token = _generate_token(cfg)
                _write_local_env(new_token)
                success("Token refreshed (valid for ~15 more min)")
            except Exception as e:
                warn(f"Token refresh failed: {e}")
    t = threading.Thread(target=refresher, daemon=True)
    t.start()


@app.command()
def refresh(env: str = typer.Argument(..., help="Environment: dev, qa, ...")):
    """Regenerate DB auth token and save to .env.local."""
    warn_deprecated("db refresh", "run db --refresh")
    DbCommand.validate_env(env)
    cfg = Config.with_env(env)

    info(f"Generating new DB token for {env}...")
    token = _generate_token(cfg)
    _write_local_env(token)
    info(f"Token expires in ~15 min. Run 'yappy db refresh {env}' to renew.")


@app.command()
def up(
    env: str = typer.Argument(..., help="Environment: dev, qa, ..."),
    auto_refresh: bool = typer.Option(
        False, "--auto-refresh", "-r",
        help="Auto-refresh token every 12 minutes",
    ),
    detach: bool = typer.Option(
        False, "--detach", "-d",
        help="Run tunnel in background",
    ),
    keep_alive: bool = typer.Option(
        False, "--keep-alive", "-k",
        help="Auto-reconnect tunnel if it drops",
    ),
):
    """Start SSM tunnel to Aurora database."""
    warn_deprecated("db up", "run db")
    DbCommand.validate_env(env)
    db_cmd.check_requirements("aws")
    cfg = Config.with_env(env)

    token = _generate_token(cfg)
    _write_local_env(token)

    if keep_alive and detach:
        die("--keep-alive and --detach are mutually exclusive")

    if auto_refresh:
        info(f"Starting auto-refresh tunnel to {env} (localhost:{cfg.db_port})...")
    else:
        info(f"Starting database tunnel to {env} (localhost:{cfg.db_port})...")

    try:
        proc = db_cmd.ssm_tunnel(
            instance=cfg.require("AWS_INSTANCE"),
            port=int(cfg.get("AWS_PORT", "53360")),
            local_port=cfg.db_port,
            region=cfg.require("AWS_REGION"),
            profile=cfg.profile,
            remote_host=cfg.require("AWS_HOST"),
            quiet=detach,
        )
    except Exception as e:
        die(f"Failed to start tunnel: {e}")

    def _restart():
        info("Regenerating token and restarting tunnel...")
        new_token = _generate_token(cfg)
        _write_local_env(new_token)
        return db_cmd.ssm_tunnel(
            instance=cfg.require("AWS_INSTANCE"),
            port=int(cfg.get("AWS_PORT", "53360")),
            local_port=cfg.db_port,
            region=cfg.require("AWS_REGION"),
            profile=cfg.profile,
            remote_host=cfg.require("AWS_HOST"),
        )

    if keep_alive:
        stop_event: threading.Event | None = None
        if auto_refresh:
            stop_event = threading.Event()
            _start_refresher(cfg, stop_event)
        try:
            db_cmd.serve_forever(proc, name=f"DB tunnel to {env}", local_port=cfg.db_port, on_restart=_restart)
        finally:
            if stop_event:
                stop_event.set()
        return

    if auto_refresh:
        success(f"Tunnel started (PID {proc.pid}) on localhost:{cfg.db_port}")
        stop_event = threading.Event()
        _start_refresher(cfg, stop_event)

        if detach:
            success("Auto-refresh tunnel running in background (use 'yappy ssm kill' to stop)")
            time.sleep(2)
            return

        info("Press Ctrl+C to stop tunnel and refresher")
        try:
            while True:
                time.sleep(2)
                if proc.poll() is not None:
                    die(f"SSM tunnel exited unexpectedly (code {proc.returncode})")
        except KeyboardInterrupt:
            info("Stopping tunnel...")
            stop_event.set()
            proc.terminate()
            proc.wait(timeout=5)
            db_cmd.kill_ssm()
            success("Tunnel stopped")
        return

    db_cmd.serve(proc, detach, name="DB tunnel", local_port=cfg.db_port)
