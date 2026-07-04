from __future__ import annotations

import subprocess
import time
from pathlib import Path

from ..config import Config
from ..logger import info, success, warn


class KafkaService:
    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._kafka_core = Path(cfg.kafka_core_path)
        self._kafka_ui = Path(cfg.kafka_ui_path)
        self._procs: list[subprocess.Popen] = []

    def up(self, target: str) -> None:
        if target == "server":
            server_bat = self._kafka_core / "bin" / "windows" / "kafka-server-start.bat"
            props = self._kafka_core / "config" / "kraft" / "server.properties"
            if not server_bat.exists():
                warn(f"Kafka server script not found: {server_bat}")
                return
            if not props.exists():
                warn(f"Kafka properties not found: {props}")
                return
            info("Starting Kafka server (KRaft)...")
            proc = subprocess.Popen(
                [str(server_bat), str(props)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            self._procs.append(proc)
            time.sleep(2)
            if proc.poll() is None:
                success("Kafka server started on localhost:9092")
            else:
                warn("Kafka server may not have started correctly")

        elif target == "ui":
            ui_jar = self._kafka_ui / "main.jar"
            if not ui_jar.exists():
                warn(f"Kafdrop UI jar not found: {ui_jar}")
                return
            info("Starting Kafdrop UI on port 8080...")
            cmd = [
                "java", "-jar", str(ui_jar),
                "--server.port=8080",
            ]
            ui_config = self._kafka_ui / "config.yml"
            if ui_config.exists():
                cmd.append(f"--spring.config.additional-location=file:{ui_config}")
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            self._procs.append(proc)
            time.sleep(2)
            if proc.poll() is None:
                success("Kafdrop UI started on http://localhost:8080")
            else:
                warn("Kafdrop UI may not have started correctly")
        else:
            warn(f"Unknown target: {target}. Use 'server' or 'ui'.")

    def cleanup(self):
        for proc in self._procs:
            if proc.poll() is None:
                proc.terminate()
        self._procs.clear()


class DevUtils:
    def __init__(self):
        self._cfg = Config()

    def kafka(self) -> KafkaService:
        return KafkaService(self._cfg)
