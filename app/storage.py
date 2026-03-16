from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from app.config import get_settings
from app.schemas import AuditRecord, JobState


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
        shutil.copyfile(source, target)
        return target

    def preview_1_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "preview_1.jpg"

    def preview_2_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "preview_2.jpg"

    def final_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "final.jpg"

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
