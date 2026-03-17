from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


def _read_payload() -> dict[str, Any]:
    if len(sys.argv) > 1:
        payload_path = Path(sys.argv[1])
    else:
        env_payload = os.getenv("PHOTO_POST_DAVINCI_PAYLOAD_PATH")
        payload_path = Path(env_payload) if env_payload else None

    if payload_path:
        return json.loads(payload_path.read_text(encoding="utf-8"))

    raw = sys.stdin.read().strip()
    if not raw:
        raise ValueError("No payload received. Provide JSON via stdin or payload file path.")
    return json.loads(raw)


def _materialize_output(payload: dict[str, Any]) -> Path:
    output_dir = Path(tempfile.gettempdir()) / "photo-post-mvp" / "davinci-bridge"
    output_dir.mkdir(parents=True, exist_ok=True)

    # This template keeps behavior deterministic for self-test and local debugging.
    # Real Resolve automation can replace this with timeline operations + render output.
    output_path = output_dir / f"round-{payload.get('round', 0)}-preview.jpg"

    source_hint = payload.get("source_path")
    if isinstance(source_hint, str) and source_hint:
        source = Path(source_hint)
        if source.exists():
            shutil.copyfile(source, output_path)
            return output_path

    output_path.write_bytes(b"DAVINCI_BRIDGE_PLACEHOLDER")
    return output_path


def main() -> int:
    try:
        payload = _read_payload()
        output_path = _materialize_output(payload)
        response = {
            "ok": True,
            "adapter": "davinci-bridge-template",
            "round": payload.get("round", 0),
            "output_path": str(output_path),
            "note": "Template bridge executed. Replace with Resolve scripting for real edits.",
        }
        json.dump(response, sys.stdout, ensure_ascii=True)
        return 0
    except Exception as exc:  # pragma: no cover
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, ensure_ascii=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
