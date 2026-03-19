from __future__ import annotations

import json
import shutil
from datetime import datetime
from io import BytesIO
from pathlib import Path

from app.config import get_settings
from app.schemas import AuditRecord, JobState

try:  # pragma: no cover - import guard for minimal environments
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


class StorageManager:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        return self.settings.data_dir / "jobs" / job_id

    def ensure_job_dirs(self, job_id: str) -> Path:
        job_dir = self.job_dir(job_id)
        (job_dir / "original").mkdir(parents=True, exist_ok=True)
        (job_dir / "audit").mkdir(parents=True, exist_ok=True)
        return job_dir

    def save_original(self, job_id: str, filename: str, content: bytes) -> Path:
        job_dir = self.ensure_job_dirs(job_id)
        safe_name = Path(filename).name or "upload.bin"
        target = job_dir / "original" / safe_name
        target.write_bytes(content)
        return target

    def export_preview(self, source: Path, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)

        # For browser-visible artifacts, try to materialize true JPEG bytes.
        if target.suffix.lower() in {".jpg", ".jpeg"} and Image is not None:
            try:
                with Image.open(source) as img:
                    img.convert("RGB").save(target, format="JPEG", quality=90, optimize=True)
                    return target
            except Exception:
                # Keep fallback behavior for unsupported formats or minimal test fixtures.
                pass

        shutil.copyfile(source, target)
        return target

    def preview_1_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "preview_1.jpg"

    def analysis_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "analysis_input.jpg"

    def preview_2_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "preview_2.jpg"

    def final_path(self, job_id: str, original_filename: str, rendered_source: Path | None = None) -> Path:
        # Keep the user's base filename, but follow the rendered file extension for compatibility.
        original = Path(original_filename).name
        stem = Path(original).stem
        if rendered_source is not None and rendered_source.suffix:
            return self.job_dir(job_id) / f"{stem}{rendered_source.suffix.lower()}"
        return self.job_dir(job_id) / original

    def export_analysis_jpeg(
        self,
        source: Path,
        target: Path,
        *,
        max_bytes: int = 5 * 1024 * 1024,
        quality_percent: int = 10,
        max_dimension: int = 2048,
    ) -> tuple[Path, dict[str, int | bool]]:
        target.parent.mkdir(parents=True, exist_ok=True)

        if Image is None:
            # Fallback when Pillow is unavailable: force a hard byte cap with truncation.
            data = source.read_bytes()
            if len(data) > max_bytes:
                data = data[:max_bytes]
            target.write_bytes(data)
            return target, {
                "used_fallback": True,
                "quality_percent": quality_percent,
                "max_dimension": max_dimension,
                "bytes": target.stat().st_size,
            }

        try:
            with Image.open(source) as img:
                converted = img.convert("RGB")
                width, height = converted.size
                longest = max(width, height)
                if longest > max_dimension:
                    scale = max_dimension / float(longest)
                    resized = converted.resize((int(width * scale), int(height * scale)))
                else:
                    resized = converted

                quality = max(5, min(95, int(quality_percent)))
                data: bytes | None = None
                while quality >= 5:
                    buffer = BytesIO()
                    resized.save(buffer, format="JPEG", quality=quality, optimize=True)
                    candidate = buffer.getvalue()
                    if len(candidate) <= max_bytes:
                        data = candidate
                        break
                    quality -= 5

                if data is None:
                    # As a hard cap fallback, force tiny dimensions and low quality.
                    tiny = resized.resize((min(1024, resized.width), min(1024, resized.height)))
                    buffer = BytesIO()
                    tiny.save(buffer, format="JPEG", quality=5, optimize=True)
                    data = buffer.getvalue()

                target.write_bytes(data)
                return target, {
                    "used_fallback": False,
                    "quality_percent": quality,
                    "max_dimension": max_dimension,
                    "bytes": len(data),
                }
        except Exception:
            # Unknown formats (for example RAW bytes in tests) still respect max_bytes.
            data = source.read_bytes()
            if len(data) > max_bytes:
                data = data[:max_bytes]
            target.write_bytes(data)
            return target, {
                "used_fallback": True,
                "quality_percent": quality_percent,
                "max_dimension": max_dimension,
                "bytes": target.stat().st_size,
            }

    def write_audit(self, job_id: str, kind: str, state: JobState, payload: dict) -> Path:
        audit_dir = self.ensure_job_dirs(job_id) / "audit"
        index = len(list(audit_dir.glob("*.json"))) + 1
        target = audit_dir / f"{index:03d}_{kind}.json"
        record = AuditRecord(
            kind=kind,
            state=state,
            payload=payload,
            created_at=datetime.utcnow(),
        )
        target.write_text(json.dumps(record.model_dump(mode="json"), indent=2), encoding="utf-8")
        return target

    def list_audits(self, job_id: str) -> list[str]:
        audit_dir = self.job_dir(job_id) / "audit"
        if not audit_dir.exists():
            return []
        return [str(path) for path in sorted(audit_dir.glob("*.json"))]
