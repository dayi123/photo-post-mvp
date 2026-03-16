#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def _read_payload() -> dict[str, Any]:
    payload_path = os.getenv("PHOTO_POST_DAVINCI_PAYLOAD_PATH")
    if payload_path:
        return json.loads(Path(payload_path).read_text(encoding="utf-8"))
    data = sys.stdin.read().strip()
    if not data:
        raise RuntimeError("No payload provided on stdin and PHOTO_POST_DAVINCI_PAYLOAD_PATH is empty.")
    return json.loads(data)


def _try_connect_resolve() -> tuple[bool, str]:
    script_api = os.getenv(
        "RESOLVE_SCRIPT_API",
        r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting",
    )
    script_lib = os.getenv(
        "RESOLVE_SCRIPT_LIB",
        r"D:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll",
    )

    modules_dir = str(Path(script_api) / "Modules")
    if modules_dir not in sys.path:
        sys.path.append(modules_dir)

    os.environ.setdefault("RESOLVE_SCRIPT_API", script_api)
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", script_lib)

    try:
        import DaVinciResolveScript as dvr_script  # type: ignore

        resolve = dvr_script.scriptapp("Resolve")
        if resolve is None:
            return False, "Resolve is not running or external scripting is disabled."

        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject() if pm else None
        project_name = project.GetName() if project else None
        page = resolve.GetCurrentPage()
        return True, f"Connected. page={page}, project={project_name}"
    except Exception as exc:  # pragma: no cover
        return False, f"Resolve API error: {exc}"


def main() -> int:
    try:
        payload = _read_payload()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"payload error: {exc}"}), file=sys.stderr)
        return 2

    ok, detail = _try_connect_resolve()
    if not ok:
        print(json.dumps({"ok": False, "error": detail, "round": payload.get("round")}), file=sys.stderr)
        return 3

    # MVP behavior: acknowledge action payload. Real grading/export can be added here.
    out = {
        "ok": True,
        "bridge": "davinci",
        "message": detail,
        "round": payload.get("round"),
        "profile": payload.get("action", {}).get("profile"),
        "adjustment_count": len(payload.get("action", {}).get("adjustments", [])),
    }
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
