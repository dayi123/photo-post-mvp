from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

try:  # pragma: no cover - import guard for minimal environments
    from PIL import Image, ImageEnhance
except Exception:  # pragma: no cover
    Image = None
    ImageEnhance = None

try:  # pragma: no cover - optional RAW decoder
    import rawpy
except Exception:  # pragma: no cover
    rawpy = None

RAW_EXTENSIONS = {".dng", ".cr2", ".cr3", ".nef", ".arw", ".rw2", ".orf", ".raf", ".pef", ".srw", ".raw"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DaVinci bridge for photo-post-mvp")
    parser.add_argument("payload", nargs="?", help="Path to payload JSON file")
    parser.add_argument("--payload", "-p", dest="payload_opt", help="Path to payload JSON file")
    parser.add_argument(
        "--mode",
        choices=["resolve", "template", "auto"],
        default=os.getenv("PHOTO_POST_DAVINCI_BRIDGE_MODE", "auto").strip().lower() or "auto",
        help="resolve: require Resolve scripting; template: lightweight local edits; auto: try resolve then fallback.",
    )
    parser.add_argument(
        "--resolve-timeout",
        type=int,
        default=int(os.getenv("PHOTO_POST_DAVINCI_RESOLVE_TIMEOUT_SECONDS", "120")),
        help="Timeout for Resolve render completion.",
    )
    return parser.parse_args()


def _read_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload_path = args.payload_opt or args.payload
    if payload_path:
        return json.loads(Path(payload_path).read_text(encoding="utf-8"))

    env_payload = os.getenv("PHOTO_POST_DAVINCI_PAYLOAD_PATH")
    if env_payload:
        return json.loads(Path(env_payload).read_text(encoding="utf-8"))

    raw = sys.stdin.read().strip()
    if not raw:
        raise ValueError("No payload received. Provide JSON via stdin or payload file path.")
    return json.loads(raw)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _load_source_image(source: Path) -> Image.Image:
    if Image is None:
        raise ValueError("Pillow is required for template bridge image processing.")

    suffix = source.suffix.lower()
    if suffix in RAW_EXTENSIONS:
        if rawpy is None:
            raise ValueError(
                "RAW input detected but rawpy is not installed. "
                "Install rawpy or run in resolve mode with DaVinci Resolve scripting enabled."
            )
        with rawpy.imread(str(source)) as raw:
            rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=False, output_bps=8)
        return Image.fromarray(rgb).convert("RGB")

    return Image.open(source).convert("RGB")


def _apply_temperature(img: Image.Image, value: float) -> Image.Image:
    amount = _clamp(value / 100.0, -1.0, 1.0)
    r_mul = 1.0 + (0.25 * amount)
    b_mul = 1.0 - (0.25 * amount)

    r, g, b = img.split()
    r = r.point(lambda px: int(_clamp(px * r_mul, 0, 255)))
    b = b.point(lambda px: int(_clamp(px * b_mul, 0, 255)))
    return Image.merge("RGB", (r, g, b))


def _apply_highlights(img: Image.Image, value: float) -> Image.Image:
    amount = _clamp(value / 100.0, -1.0, 1.0)

    def remap(px: int) -> int:
        if px < 128:
            return px
        delta = (px - 128) * 0.5 * amount
        return int(_clamp(px - delta, 0, 255))

    channels = [channel.point(remap) for channel in img.split()]
    return Image.merge("RGB", tuple(channels))


def _apply_shadows(img: Image.Image, value: float) -> Image.Image:
    amount = _clamp(value / 100.0, -1.0, 1.0)

    def remap(px: int) -> int:
        if px > 127:
            return px
        delta = (128 - px) * 0.5 * amount
        return int(_clamp(px + delta, 0, 255))

    channels = [channel.point(remap) for channel in img.split()]
    return Image.merge("RGB", tuple(channels))


def _apply_crop(img: Image.Image, value: float) -> Image.Image:
    ratio = _clamp(abs(value) / 100.0, 0.0, 1.0) * 0.30
    if ratio <= 0.001:
        return img

    width, height = img.size
    dx = int(width * ratio / 2.0)
    dy = int(height * ratio / 2.0)
    if dx < 1 or dy < 1:
        return img

    return img.crop((dx, dy, width - dx, height - dy))


def _apply_straighten(img: Image.Image, value: float) -> Image.Image:
    angle = _clamp(value, -100.0, 100.0) * 0.3
    if abs(angle) < 0.05:
        return img
    return img.rotate(-angle, expand=True, fillcolor=(0, 0, 0))


def _apply_adjustments(img: Image.Image, adjustments: list[dict[str, Any]]) -> Image.Image:
    out = img
    for item in adjustments:
        op = str(item.get("op", "")).lower()
        value = float(item.get("value", 0.0))

        if op == "exposure" and ImageEnhance is not None:
            factor = 1.0 + (value / 100.0)
            out = ImageEnhance.Brightness(out).enhance(_clamp(factor, 0.05, 2.5))
        elif op == "contrast" and ImageEnhance is not None:
            factor = 1.0 + (value / 100.0)
            out = ImageEnhance.Contrast(out).enhance(_clamp(factor, 0.05, 3.0))
        elif op == "saturation" and ImageEnhance is not None:
            factor = 1.0 + (value / 100.0)
            out = ImageEnhance.Color(out).enhance(_clamp(factor, 0.0, 3.0))
        elif op == "temperature":
            out = _apply_temperature(out, value)
        elif op == "highlights":
            out = _apply_highlights(out, value)
        elif op == "shadows":
            out = _apply_shadows(out, value)
        elif op == "crop":
            out = _apply_crop(out, value)
        elif op == "straighten":
            out = _apply_straighten(out, value)

    return out


def _materialize_template_output(payload: dict[str, Any]) -> Path:
    source_hint = payload.get("source_path")
    if not isinstance(source_hint, str) or not source_hint.strip():
        raise ValueError("Missing source_path in payload.")

    source = Path(source_hint)
    if not source.exists():
        raise ValueError(f"source_path does not exist: {source}")

    action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
    adjustments = action.get("adjustments") if isinstance(action.get("adjustments"), list) else []
    export_format = str(action.get("export_format") or "jpg").lower()
    if export_format not in {"jpg", "jpeg", "png"}:
        export_format = "jpg"

    output_dir = Path(tempfile.gettempdir()) / "photo-post-mvp" / "davinci-bridge"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"round-{payload.get('round', 0)}-preview.{export_format}"

    img = _load_source_image(source)
    edited = _apply_adjustments(img, adjustments)

    if export_format in {"jpg", "jpeg"}:
        edited.convert("RGB").save(output_path, format="JPEG", quality=92, optimize=True)
    else:
        edited.save(output_path, format="PNG")

    return output_path


def _try_import_resolve_module() -> Any:
    try:
        return importlib.import_module("DaVinciResolveScript")
    except ImportError:
        pass

    # Common install paths for Resolve scripting modules.
    candidate_dirs = [
        os.getenv("RESOLVE_SCRIPT_API"),
        r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
        "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
        "/opt/resolve/Developer/Scripting/Modules",
    ]
    for directory in candidate_dirs:
        if not directory:
            continue
        module_dir = Path(directory)
        if not module_dir.exists():
            continue
        if str(module_dir) not in sys.path:
            sys.path.insert(0, str(module_dir))
        try:
            return importlib.import_module("DaVinciResolveScript")
        except ImportError:
            continue

    raise RuntimeError(
        "Cannot import DaVinciResolveScript. Set RESOLVE_SCRIPT_API to Resolve Scripting/Modules path."
    )


def _find_output_file(target_dir: Path, base_name: str) -> Path:
    candidates = sorted(target_dir.glob(f"{base_name}*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError(f"Resolve render finished but no output found in {target_dir} for prefix {base_name}.")
    return candidates[0]


def _map_resolve_format(export_format: str) -> tuple[str, str]:
    normalized = export_format.lower()
    if normalized == "png":
        return "png", "RGB8"
    return "jpg", "RGB8"


def _materialize_resolve_output(payload: dict[str, Any], timeout_seconds: int) -> Path:
    source_hint = payload.get("source_path")
    if not isinstance(source_hint, str) or not source_hint.strip():
        raise ValueError("Missing source_path in payload.")

    source = Path(source_hint)
    if not source.exists():
        raise ValueError(f"source_path does not exist: {source}")

    resolve_script = _try_import_resolve_module()
    resolve = resolve_script.scriptapp("Resolve")
    if resolve is None:
        raise RuntimeError("Cannot attach to DaVinci Resolve. Please launch Resolve first.")

    project_manager = resolve.GetProjectManager()
    if project_manager is None:
        raise RuntimeError("Resolve project manager is unavailable.")
    project = project_manager.GetCurrentProject()
    if project is None:
        raise RuntimeError("No active Resolve project. Open a project and try again.")

    media_pool = project.GetMediaPool()
    if media_pool is None:
        raise RuntimeError("Resolve media pool is unavailable.")

    clips = media_pool.ImportMedia([str(source)])
    if not clips:
        raise RuntimeError(f"Resolve failed to import source media: {source}")

    round_id = payload.get("round", 0)
    timeline_name = f"photo-post-mvp-{int(time.time())}-{round_id}"
    timeline = media_pool.CreateTimelineFromClips(timeline_name, clips)
    if timeline is None:
        raise RuntimeError("Resolve failed to create timeline from imported clip.")

    project.SetCurrentTimeline(timeline)

    action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
    export_format = str(action.get("export_format") or "jpg")
    render_format, render_codec = _map_resolve_format(export_format)

    output_dir = Path(tempfile.gettempdir()) / "photo-post-mvp" / "davinci-resolve"
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"round-{round_id}-resolve"

    ok = project.SetRenderSettings(
        {
            "TargetDir": str(output_dir),
            "CustomName": base_name,
            "SelectAllFrames": 1,
            "Format": render_format,
            "VideoCodec": render_codec,
        }
    )
    if not ok:
        raise RuntimeError("Resolve rejected render settings.")

    job_id = project.AddRenderJob()
    if not job_id:
        raise RuntimeError("Resolve failed to create render job.")

    started = project.StartRendering(job_id)
    if started is False:
        raise RuntimeError("Resolve failed to start render job.")

    deadline = time.time() + timeout_seconds
    while True:
        if not project.IsRenderingInProgress():
            break
        if time.time() >= deadline:
            try:
                project.StopRendering()
            except Exception:
                pass
            raise RuntimeError(f"Resolve render timed out after {timeout_seconds} seconds.")
        time.sleep(0.5)

    return _find_output_file(output_dir, base_name)


def main() -> int:
    try:
        args = _parse_args()
        payload = _read_payload(args)

        if args.mode == "template":
            output_path = _materialize_template_output(payload)
            response = {
                "ok": True,
                "adapter": "davinci-bridge-template",
                "round": payload.get("round", 0),
                "output_path": str(output_path),
                "note": "Template bridge applied lightweight edits.",
            }
            json.dump(response, sys.stdout, ensure_ascii=True)
            return 0

        try:
            output_path = _materialize_resolve_output(payload, timeout_seconds=args.resolve_timeout)
            response = {
                "ok": True,
                "adapter": "davinci-bridge-resolve",
                "round": payload.get("round", 0),
                "output_path": str(output_path),
                "note": "Rendered via DaVinci Resolve scripting.",
            }
            json.dump(response, sys.stdout, ensure_ascii=True)
            return 0
        except Exception as resolve_error:
            if args.mode == "resolve":
                raise

            output_path = _materialize_template_output(payload)
            response = {
                "ok": True,
                "adapter": "davinci-bridge-template",
                "round": payload.get("round", 0),
                "output_path": str(output_path),
                "note": f"Resolve mode unavailable; fell back to template bridge. reason={resolve_error}",
            }
            json.dump(response, sys.stdout, ensure_ascii=True)
            return 0

    except Exception as exc:  # pragma: no cover
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, ensure_ascii=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
