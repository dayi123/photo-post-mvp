from __future__ import annotations

import json
import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.schemas import Action, RuntimeConfig


class EditorAdapterError(RuntimeError):
    pass


class EditorAdapter(ABC):
    @abstractmethod
    def apply_action(self, action: Action, round_number: int) -> dict[str, Any]:
        raise NotImplementedError


class StubAdapter(EditorAdapter):
    def apply_action(self, action: Action, round_number: int) -> dict[str, Any]:
        return {
            "adapter": "stub",
            "round": round_number,
            "adjustment_count": len(action.adjustments),
            "status": "applied",
        }


class DaVinciAdapter(EditorAdapter):
    def __init__(self, command: str | None, input_mode: str = "stdin", timeout_seconds: int = 60) -> None:
        self.command = (command or "").strip()
        self.input_mode = input_mode.strip().lower()
        self.timeout_seconds = timeout_seconds

    def apply_action(self, action: Action, round_number: int) -> dict[str, Any]:
        if not self.command:
            raise EditorAdapterError("davinci_cmd is required when editor_backend=davinci.")
        if self.input_mode not in {"stdin", "file"}:
            raise EditorAdapterError("davinci_input_mode must be either 'stdin' or 'file'.")

        payload = json.dumps(
            {
                "round": round_number,
                "action": action.model_dump(mode="json"),
            }
        )
        command = self.command
        env = os.environ.copy()
        stdin_data = None
        payload_path: Path | None = None

        if self.input_mode == "stdin":
            stdin_data = payload.encode("utf-8")
        else:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
                handle.write(payload)
                payload_path = Path(handle.name)
            env["PHOTO_POST_DAVINCI_PAYLOAD_PATH"] = str(payload_path)
            command = command.replace("{payload_path}", str(payload_path))

        try:
            completed = subprocess.run(
                command,
                shell=True,
                input=stdin_data,
                capture_output=True,
                timeout=self.timeout_seconds,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise EditorAdapterError(
                f"DaVinci command timed out after {self.timeout_seconds} seconds."
            ) from exc
        except OSError as exc:
            raise EditorAdapterError(f"Failed to start DaVinci command: {exc}") from exc
        finally:
            if payload_path and payload_path.exists():
                payload_path.unlink()

        stdout_text = completed.stdout.decode("utf-8", errors="replace").strip()
        stderr_text = completed.stderr.decode("utf-8", errors="replace").strip()

        if completed.returncode != 0:
            detail = stderr_text or stdout_text or "no output"
            raise EditorAdapterError(
                f"DaVinci command failed with exit code {completed.returncode}: {detail}"
            )

        return {
            "adapter": "davinci",
            "round": round_number,
            "status": "applied",
            "input_mode": self.input_mode,
            "command": command,
            "output": self._parse_output(stdout_text),
            "stderr": stderr_text or None,
        }

    @staticmethod
    def _parse_output(stdout_text: str) -> Any:
        if not stdout_text:
            return None
        try:
            return json.loads(stdout_text)
        except json.JSONDecodeError:
            return {"text": stdout_text}


def build_editor_adapter(config: RuntimeConfig) -> EditorAdapter:
    backend = config.editor_backend.strip().lower()
    if backend == "stub":
        return StubAdapter()
    if backend == "davinci":
        return DaVinciAdapter(
            command=config.davinci_cmd,
            input_mode=config.davinci_input_mode,
            timeout_seconds=config.davinci_timeout_seconds,
        )
    raise EditorAdapterError("editor_backend must be either 'stub' or 'davinci'.")
