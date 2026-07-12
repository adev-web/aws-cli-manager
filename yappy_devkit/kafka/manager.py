import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import typer

from ..base import BaseCommand
from ..config import Config
from ..deprecation import warn_deprecated
from ..logger import success, info, warn, die, raw

app = typer.Typer(help="Local Kafka management")
_cfg = Config()


class KafkaCommand(BaseCommand):
    @property
    def _kafka_core(self) -> Path:
        return Path(_cfg.kafka_core_path)

    @property
    def _kafka_ui(self) -> Path:
        return Path(_cfg.kafka_ui_path)

    def _bin(self, script: str) -> Path:
        return self._kafka_core / "bin" / "windows" / script

    def _kafka_run(self, cmd: list[str], **kwargs):
        log = " ".join(str(c) for c in cmd)
        info(f"Running: {log}")
        return subprocess.run(cmd, **kwargs)


kafka_cmd = KafkaCommand()


def _kill_kafka_processes():
    try:
        result = subprocess.run(["jps", "-l"], capture_output=True, text=True, check=False)
        for line in result.stdout.strip().splitlines():
            parts = line.strip().split()
            if len(parts) == 2:
                pid, name = parts
                if "kafka.Kafka" in name or "main.jar" in name:
                    raw(f"  - matando proceso {name} (PID {pid})")
                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
        time.sleep(1)
    except FileNotFoundError:
        warn("jps no encontrado, no se pudieron buscar procesos Java")


def _on_rm_error(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


@app.command()
def up(
    action: str = typer.Argument(..., help="server, ui, or clean"),
    detach: bool = typer.Option(False, "--detach", "-d", help="Run in background"),
):
    """Start local Kafka (server), UI (kafdrop), or clean (reset storage)."""
    warn_deprecated("kafka up", "run kafka")
    if action not in ("server", "ui", "clean"):
        die("Invalid action. Use: server, ui, or clean")

    if action == "server":
        server_bat = kafka_cmd._bin("kafka-server-start.bat")
        props = kafka_cmd._kafka_core / "config" / "kraft" / "server.properties"
        if not server_bat.exists():
            die(f"Kafka server script not found: {server_bat}")
        if not props.exists():
            die(f"Kafka properties not found: {props}")
        info("Starting Kafka server (KRaft)...")

        cmd = [str(server_bat), str(props)]

        if detach:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            success("Kafka server started (background)")
            time.sleep(2)
        else:
            try:
                subprocess.run(cmd, check=False)
            except KeyboardInterrupt:
                success("Kafka server stopped (Ctrl+C)")

    elif action == "ui":
        ui_jar = kafka_cmd._kafka_ui / "main.jar"
        if not ui_jar.exists():
            die(f"Kafdrop UI jar not found: {ui_jar}")
        info("Starting Kafdrop UI on port 8080...")

        cmd = [
            "java", "-jar", str(ui_jar),
            "--server.port=8080",
            f"--spring.config.additional-location=file:{kafka_cmd._kafka_ui / 'config.yml'}",
        ]

        if detach:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            success("Kafdrop UI started (background)")
            time.sleep(2)
        else:
            try:
                subprocess.run(cmd, check=False)
            except KeyboardInterrupt:
                success("Kafdrop UI stopped (Ctrl+C)")

    elif action == "clean":
        logs_dir = kafka_cmd._kafka_core / "temp" / "kraft" / "kafka-logs"
        kafka_logs = kafka_cmd._kafka_core / "logs"

        raw("Reiniciando el almacenamiento de Kafka...")
        raw("")
        raw("Limpiando archivos temporales y logs de Kafka...")

        _kill_kafka_processes()

        import shutil

        def _rm(path: Path):
            if not path.exists():
                return
            try:
                shutil.rmtree(path, onerror=_on_rm_error)
                raw(f"  - logs eliminados: {path.name}")
            except PermissionError as e:
                raw(f"  - no se pudo eliminar {path}: {e}")

        _rm(logs_dir)
        _rm(kafka_logs)

        raw("")
        storage_bat = kafka_cmd._bin("kafka-storage.bat")
        props = kafka_cmd._kafka_core / "config" / "kraft" / "server.properties"

        raw("Generando nuevo UUID para el storage...")
        result = subprocess.run(
            [str(storage_bat), "random-uuid"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            die(f"Error generando UUID: {result.stderr.strip()}")
        uuid = result.stdout.strip()
        raw(f"  UUID: {uuid}")

        raw("Formateando el storage...")
        result = subprocess.run(
            [str(storage_bat), "format", "-t", uuid, "-c", str(props)],
            capture_output=True, text=True, check=False,
        )
        if "Formatting" in result.stdout or result.returncode == 0:
            raw("Storage reset completado")
        else:
            die(f"Error formateando storage: {result.stderr.strip()}")


def _kill_ui_process():
    try:
        result = subprocess.run(["jps", "-l"], capture_output=True, text=True, check=False)
        killed = False
        for line in result.stdout.strip().splitlines():
            parts = line.strip().split()
            if len(parts) == 2:
                pid, name = parts
                if "main.jar" in name:
                    raw(f"  - matando UI (PID {pid})")
                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                    killed = True
        if not killed:
            warn("No se encontró proceso de Kafka UI")
        else:
            time.sleep(1)
            success("Kafdrop UI stopped")
    except FileNotFoundError:
        warn("jps no encontrado, no se pudieron buscar procesos Java")


@app.command()
def down(
    target: str = typer.Argument("server", help="server or ui"),
):
    """Stop local Kafka server or UI."""
    warn_deprecated("kafka down", "stop kafka")
    if target not in ("server", "ui"):
        die("Invalid target. Use: server or ui")

    if target == "server":
        stop_bat = kafka_cmd._bin("kafka-server-stop.bat")
        if not stop_bat.exists():
            die(f"Kafka stop script not found: {stop_bat}")
        info("Waiting for Kafka to stop...")
        subprocess.run([str(stop_bat)], check=False)
        success("Kafka server stopped")
    elif target == "ui":
        info("Stopping Kafdrop UI...")
        _kill_ui_process()
