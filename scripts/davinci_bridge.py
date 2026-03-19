from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
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


def _payload_path_from_argv() -> Path | None:
    argv = sys.argv[1:]
    if not argv:
        return None

    if argv[0] in {"--payload", "-p"}:
        if len(argv) < 2:
            raise ValueError("Missing payload path after --payload.")
        return Path(argv[1])

    return Path(argv[0])


def _read_payload() -> dict[str, Any]:
    payload_path = _payload_path_from_argv()

    if payload_path:
        return json.loads(payload_path.read_text(encoding="utf-8"))

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
                "Install rawpy or replace this bridge with real Resolve automation."
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


def _materialize_output(payload: dict[str, Any]) -> Path:
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


def main() -> int:
    try:
        payload = _read_payload()
        output_path = _materialize_output(payload)
        response = {
            "ok": True,
            "adapter": "davinci-bridge-template",
            "round": payload.get("round", 0),
            "output_path": str(output_path),
            "note": "Template bridge applied lightweight edits. Replace with Resolve scripting for production color work.",
        }
        json.dump(response, sys.stdout, ensure_ascii=True)
        return 0
    except Exception as exc:  # pragma: no cover
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, ensure_ascii=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
