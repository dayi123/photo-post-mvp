from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlmodel import Session

from app.config import get_settings
from app.models import Job
from app.schemas import Action, JobRead, JobState, Plan, Review, RuntimeConfig
from app.services import llm_stub, prompt_templates
from app.services.editor_adapters import build_editor_adapter
from app.services.llm_client import LlmClient, LlmClientError
from app.services.runtime_settings import RuntimeSettingsService
from app.storage import StorageManager


ALLOWED_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.RECEIVED: {JobState.PREVIEW_1_EXPORTED, JobState.FAILED},
    JobState.PREVIEW_1_EXPORTED: {JobState.PLAN_GENERATED, JobState.FAILED},
    JobState.PLAN_GENERATED: {JobState.WAIT_USER_CONFIRM, JobState.FAILED},
    JobState.WAIT_USER_CONFIRM: {JobState.ACTION_GENERATED, JobState.FAILED},
    JobState.ACTION_GENERATED: {JobState.EDIT_APPLIED, JobState.FAILED},
    JobState.EDIT_APPLIED: {JobState.PREVIEW_2_EXPORTED, JobState.FAILED},
    JobState.PREVIEW_2_EXPORTED: {JobState.QUALITY_CHECKED, JobState.FAILED},
    JobState.QUALITY_CHECKED: {JobState.ACTION_GENERATED, JobState.FINAL_EXPORTED, JobState.FAILED},
    JobState.FINAL_EXPORTED: {JobState.DELIVERED_ARCHIVED, JobState.FAILED},
    JobState.DELIVERED_ARCHIVED: set(),
    JobState.FAILED: {
        JobState.RECEIVED,
        JobState.PREVIEW_1_EXPORTED,
        JobState.WAIT_USER_CONFIRM,
        JobState.ACTION_GENERATED,
    },
}

RAW_EXTENSIONS = {".dng", ".cr2", ".cr3", ".nef", ".arw", ".rw2", ".orf", ".raf", ".pef", ".srw", ".raw"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", *RAW_EXTENSIONS}


class JobService:
    def __init__(self) -> None:
        self.storage = StorageManager()
        self.settings = get_settings()
        self.runtime_settings = RuntimeSettingsService(self.settings)
        self.llm_client = LlmClient()

    def create_job(
        self,
        session: Session,
        upload: UploadFile,
        desired_effect: str | None = None,
    ) -> Job:
        self._validate_upload(upload)
        payload = upload.file.read()
        if not payload:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

        normalized_effect = desired_effect.strip() if isinstance(desired_effect, str) else None
        job = self._create_empty_job(session, Path(upload.filename or "upload.jpg").name)
        job.desired_effect = normalized_effect or None
        original_path = self.storage.save_original(job.id, job.original_filename, payload)
        job.original_path = str(original_path)
        return self._run_created_job(session, job)

    def create_job_from_local_path(
        self,
        session: Session,
        local_path: str,
        desired_effect: str | None = None,
    ) -> Job:
        source = Path(local_path).expanduser()
        if not source.exists() or not source.is_file():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Local photo path does not exist.")

        suffix = source.suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type. Use jpg, jpeg, png, webp, or common RAW formats.",
            )

        payload = source.read_bytes()
        if not payload:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected local file is empty.")

        job = self._create_empty_job(session, source.name)
        job.desired_effect = desired_effect
        original_path = self.storage.save_original(job.id, source.name, payload)
        job.original_path = str(original_path)
        self.storage.write_audit(job.id, "local_path_selected", job.state, {"source_path": str(source)})
        return self._run_created_job(session, job)

    def get_job(self, session: Session, job_id: str) -> Job:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        return job

    def get_plan(self, session: Session, job_id: str) -> Plan:
        job = self.get_job(session, job_id)
        if not job.plan_json:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not available yet.")
        return Plan.model_validate_json(job.plan_json)

    def confirm_plan(self, session: Session, job_id: str) -> Job:
        job = self.get_job(session, job_id)
        if job.state in {JobState.FINAL_EXPORTED, JobState.DELIVERED_ARCHIVED}:
            return job
        if job.state != JobState.WAIT_USER_CONFIRM:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job is in state {job.state} and cannot confirm plan.",
            )

        # Stage B runs after user confirmation, so honor the latest saved runtime settings.
        latest_runtime_config = self.runtime_settings.load()
        job.runtime_settings_json = latest_runtime_config.model_dump_json()
        self._persist(job, session)
        self.storage.write_audit(
            job.id,
            "runtime_settings_snapshot_confirm",
            job.state,
            self.runtime_settings.to_audit_payload(latest_runtime_config),
        )

        try:
            self._run_stage_b(job, session)
        except HTTPException:
            raise
        except Exception as exc:
            self._fail_job(job, session, str(exc))
            raise HTTPException(status_code=500, detail=f"Stage B failed: {exc}") from exc

        return self._refresh(session, job.id)

    def retry(self, session: Session, job_id: str) -> Job:
        job = self.get_job(session, job_id)
        if job.state in {JobState.WAIT_USER_CONFIRM, JobState.DELIVERED_ARCHIVED}:
            return job
        if job.state != JobState.FAILED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Retry is only allowed for FAILED jobs. Current state: {job.state}.",
            )

        job.error_message = None
        job.review_rounds = 0
        job.action_json = None
        job.review_json = None

        latest_runtime_config = self.runtime_settings.load()
        job.runtime_settings_json = latest_runtime_config.model_dump_json()
        self._persist(job, session)
        self.storage.write_audit(
            job.id,
            "runtime_settings_snapshot_retry",
            job.state,
            self.runtime_settings.to_audit_payload(latest_runtime_config),
        )

        try:
            if job.plan_json:
                self._transition(job, session, JobState.ACTION_GENERATED, allow_from_failed=True)
                self._run_stage_b(job, session, resume_from_generated=True)
            else:
                self._transition(job, session, JobState.RECEIVED, allow_from_failed=True)
                self._run_stage_a(job, session)
        except Exception as exc:
            self._fail_job(job, session, str(exc))
            raise HTTPException(status_code=500, detail=f"Retry failed: {exc}") from exc

        return self._refresh(session, job.id)

    def read_action(self, job: Job) -> Action | None:
        return Action.model_validate_json(job.action_json) if job.action_json else None

    def read_review(self, job: Job) -> Review | None:
        return Review.model_validate_json(job.review_json) if job.review_json else None

    def to_read(self, job: Job) -> JobRead:
        return JobRead(
            id=job.id,
            state=job.state,
            original_filename=job.original_filename,
            desired_effect=job.desired_effect,
            review_rounds=job.review_rounds,
            error_message=job.error_message,
            preview_1_path=job.preview_1_path,
            preview_2_path=job.preview_2_path,
            final_path=job.final_path,
            created_at=job.created_at,
            updated_at=job.updated_at,
            result_ready=job.state == JobState.DELIVERED_ARCHIVED and bool(job.final_path),
        )

    def _run_stage_a(self, job: Job, session: Session) -> None:
        if not job.original_path:
            raise ValueError("Original file is missing.")
        original_path = Path(job.original_path)
        runtime_config = self._runtime_config_for_job(job)

        preview_1 = self.storage.export_preview(original_path, self.storage.preview_1_path(job.id))
        job.preview_1_path = str(preview_1)
        self._transition(job, session, JobState.PREVIEW_1_EXPORTED)
        self.storage.write_audit(job.id, "preview_1_exported", job.state, {"preview_1_path": str(preview_1)})

        analysis_path, analysis_meta = self.storage.export_analysis_jpeg(
            original_path,
            self.storage.analysis_path(job.id),
            max_bytes=5 * 1024 * 1024,
            quality_percent=10,
        )
        self.storage.write_audit(
            job.id,
            "analysis_input_exported",
            job.state,
            {
                "analysis_input_path": str(analysis_path),
                **analysis_meta,
            },
        )

        plan_prompt = prompt_templates.build_plan_prompt(
            original_filename=job.original_filename,
            model=runtime_config.llm_model,
            override=runtime_config.plan_template_pack,
            desired_effect=job.desired_effect,
        )
        plan_request_payload = self.runtime_settings.build_plan_request_payload(
            runtime_config,
            job.original_filename,
            analysis_image_path=analysis_path,
            desired_effect=job.desired_effect,
        )
        plan, plan_execution = self._generate_plan(
            runtime_config,
            job.original_filename,
            plan_request_payload,
            desired_effect=job.desired_effect,
        )
        job.plan_json = plan.model_dump_json()
        self._transition(job, session, JobState.PLAN_GENERATED)
        self.storage.write_audit(
            job.id,
            "plan_generated",
            job.state,
            {
                "plan": json.loads(plan.model_dump_json()),
                "llm_execution": plan_execution,
                "prompt_template": {
                    "selected_pack": plan_prompt.pack,
                    "rendered_prompt": plan_prompt.text,
                },
                "prepared_request_payload": plan_request_payload,
            },
        )

        self._transition(job, session, JobState.WAIT_USER_CONFIRM)
        self.storage.write_audit(job.id, "wait_user_confirm", job.state, {"message": "Awaiting user confirmation."})

    def _run_stage_b(self, job: Job, session: Session, resume_from_generated: bool = False) -> None:
        if not job.plan_json:
            raise ValueError("Plan is not available.")
        if not job.original_path:
            raise ValueError("Original file is missing.")

        plan = Plan.model_validate_json(job.plan_json)
        runtime_config = self._runtime_config_for_job(job)
        editor_adapter = build_editor_adapter(runtime_config)
        approved = False
        start_round = job.review_rounds + 1

        for round_number in range(start_round, self.settings.max_review_rounds + 1):
            if not resume_from_generated or round_number > start_round:
                self._transition(job, session, JobState.ACTION_GENERATED)

            action_prompt = prompt_templates.build_action_prompt(
                plan=plan,
                review_round=round_number,
                model=runtime_config.llm_model,
                override=runtime_config.action_template_pack,
            )
            action_request_payload = self.runtime_settings.build_action_request_payload(
                runtime_config,
                plan,
                round_number,
            )
            action, action_execution = self._generate_action(runtime_config, plan, round_number, action_request_payload)
            job.action_json = action.model_dump_json()
            self._persist(job, session)
            self.storage.write_audit(
                job.id,
                f"action_generated_round_{round_number}",
                job.state,
                {
                    "action": json.loads(action.model_dump_json()),
                    "llm_execution": action_execution,
                    "prompt_template": {
                        "selected_pack": action_prompt.pack,
                        "rendered_prompt": action_prompt.text,
                        "json_schema_contract_summary": action_prompt.contract_summary,
                    },
                    "prepared_request_payload": action_request_payload,
                },
            )

            adapter_result = editor_adapter.apply_action(
                action,
                round_number,
                source_path=Path(job.original_path),
            )
            self._transition(job, session, JobState.EDIT_APPLIED)
            self.storage.write_audit(job.id, f"edit_applied_round_{round_number}", job.state, adapter_result)

            edited_path = self._resolve_adapter_output_path(adapter_result)
            if runtime_config.editor_backend == "davinci":
                if not edited_path or not edited_path.exists():
                    raise ValueError(
                        "DaVinci did not return a valid output_path. "
                        "Please ensure your davinci_cmd prints JSON with output_path pointing to a rendered file."
                    )
                preview_source = edited_path
            else:
                preview_source = edited_path if edited_path and edited_path.exists() else Path(job.original_path)
            preview_2 = self.storage.export_preview(preview_source, self.storage.preview_2_path(job.id))
            job.preview_2_path = str(preview_2)
            self._transition(job, session, JobState.PREVIEW_2_EXPORTED)
            self.storage.write_audit(
                job.id,
                f"preview_2_exported_round_{round_number}",
                job.state,
                {"preview_2_path": str(preview_2)},
            )

            review_request_payload = self.runtime_settings.build_review_request_payload(runtime_config, round_number)
            review, review_execution = self._review_output(runtime_config, round_number, review_request_payload)
            job.review_json = review.model_dump_json()
            job.review_rounds = round_number
            self._transition(job, session, JobState.QUALITY_CHECKED)
            self.storage.write_audit(
                job.id,
                f"quality_checked_round_{round_number}",
                job.state,
                {
                    "review": json.loads(review.model_dump_json()),
                    "llm_execution": review_execution,
                    "prepared_request_payload": review_request_payload,
                },
            )

            if review.approved:
                final_source = preview_source
                final_path = self.storage.export_preview(
                    final_source,
                    self.storage.final_path(job.id, job.original_filename, rendered_source=final_source),
                )
                job.final_path = str(final_path)
                self._transition(job, session, JobState.FINAL_EXPORTED)
                self.storage.write_audit(job.id, "final_exported", job.state, {"final_path": str(final_path)})
                self._transition(job, session, JobState.DELIVERED_ARCHIVED)
                self.storage.write_audit(job.id, "delivered_archived", job.state, {"archived": True})
                approved = True
                break

            resume_from_generated = False

        if not approved:
            self._fail_job(job, session, "Maximum review rounds reached without approval.")

    def _generate_plan(
        self,
        runtime_config: RuntimeConfig,
        original_filename: str,
        prepared_payload: dict[str, object],
        desired_effect: str | None = None,
    ) -> tuple[Plan, dict[str, object]]:
        if not runtime_config.llm_api_key:
            return llm_stub.generate_plan(
                original_filename,
                desired_effect=desired_effect,
            ), self.runtime_settings.llm_stub_audit_payload(runtime_config)

        request = self.runtime_settings.build_llm_execute_request(runtime_config, prepared_payload)
        try:
            plan = self.llm_client.generate_plan(request, runtime_config.llm_provider)
            return plan, {
                "execution_backend": "remote_llm",
                "configured_provider": runtime_config.llm_provider,
                "configured_model": runtime_config.llm_model,
                "llm_api_key_configured": True,
                "note": "Plan generated via remote LLM.",
            }
        except (LlmClientError, ValueError) as exc:
            fallback = self.runtime_settings.llm_stub_audit_payload(runtime_config)
            fallback["note"] = f"Remote LLM failed for plan; used local stub fallback. reason={exc}"
            return llm_stub.generate_plan(original_filename, desired_effect=desired_effect), fallback

    def _generate_action(
        self,
        runtime_config: RuntimeConfig,
        plan: Plan,
        review_round: int,
        prepared_payload: dict[str, object],
    ) -> tuple[Action, dict[str, object]]:
        if not runtime_config.llm_api_key:
            return llm_stub.generate_action(plan, review_round), self.runtime_settings.llm_stub_audit_payload(runtime_config)

        request = self.runtime_settings.build_llm_execute_request(runtime_config, prepared_payload)
        try:
            action = self.llm_client.generate_action(request, runtime_config.llm_provider)
            return action, {
                "execution_backend": "remote_llm",
                "configured_provider": runtime_config.llm_provider,
                "configured_model": runtime_config.llm_model,
                "llm_api_key_configured": True,
                "note": "Action generated via remote LLM.",
            }
        except (LlmClientError, ValueError) as exc:
            fallback = self.runtime_settings.llm_stub_audit_payload(runtime_config)
            fallback["note"] = f"Remote LLM failed for action; used local stub fallback. reason={exc}"
            return llm_stub.generate_action(plan, review_round), fallback

    def _review_output(
        self,
        runtime_config: RuntimeConfig,
        review_round: int,
        prepared_payload: dict[str, object],
    ) -> tuple[Review, dict[str, object]]:
        if not runtime_config.llm_api_key:
            return llm_stub.review_output(review_round), self.runtime_settings.llm_stub_audit_payload(runtime_config)

        request = self.runtime_settings.build_llm_execute_request(runtime_config, prepared_payload)
        try:
            review = self.llm_client.review_output(request, runtime_config.llm_provider)
            return review, {
                "execution_backend": "remote_llm",
                "configured_provider": runtime_config.llm_provider,
                "configured_model": runtime_config.llm_model,
                "llm_api_key_configured": True,
                "note": "Review generated via remote LLM.",
            }
        except (LlmClientError, ValueError) as exc:
            fallback = self.runtime_settings.llm_stub_audit_payload(runtime_config)
            fallback["note"] = f"Remote LLM failed for review; used local stub fallback. reason={exc}"
            return llm_stub.review_output(review_round), fallback

    def _llm_mode_audit_payload(self, runtime_config: RuntimeConfig) -> dict[str, object]:
        if runtime_config.llm_api_key:
            return {
                "execution_backend": "remote_llm_with_stub_fallback",
                "configured_provider": runtime_config.llm_provider,
                "configured_model": runtime_config.llm_model,
                "llm_api_key_configured": True,
                "note": "Remote LLM is enabled. Stub is only used as fallback when remote parsing/call fails.",
            }
        return self.runtime_settings.llm_stub_audit_payload(runtime_config)

    def _validate_upload(self, upload: UploadFile) -> None:
        filename = upload.filename or ""
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type. Use jpg, jpeg, png, webp, or common RAW formats.",
            )

        content_type = (upload.content_type or "").lower()
        if not content_type:
            return
        if content_type.startswith("image/"):
            return
        # Browsers and desktop clients often mark RAW uploads as octet-stream.
        if suffix in RAW_EXTENSIONS and content_type in {"application/octet-stream", "binary/octet-stream"}:
            return

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported content type. Expected an image or RAW upload.",
        )

    def _transition(
        self,
        job: Job,
        session: Session,
        new_state: JobState,
        allow_from_failed: bool = False,
    ) -> None:
        if job.state == new_state:
            return
        allowed = ALLOWED_TRANSITIONS.get(job.state, set())
        if allow_from_failed and job.state == JobState.FAILED:
            allowed = allowed | {new_state}
        if new_state not in allowed:
            raise ValueError(f"Invalid state transition {job.state} -> {new_state}")
        job.state = new_state
        self._persist(job, session)

    def _persist(self, job: Job, session: Session) -> None:
        job.updated_at = datetime.utcnow()
        session.add(job)
        session.commit()
        session.refresh(job)

    def _refresh(self, session: Session, job_id: str) -> Job:
        job = self.get_job(session, job_id)
        session.refresh(job)
        return job

    def _fail_job(self, job: Job, session: Session, message: str) -> None:
        job.error_message = message
        if job.state != JobState.FAILED:
            self._transition(job, session, JobState.FAILED)
        else:
            self._persist(job, session)
        self.storage.write_audit(job.id, "failed", job.state, {"error_message": message})

    def _create_empty_job(self, session: Session, filename: str) -> Job:
        job = Job(id=str(uuid4()), original_filename=filename)
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

    def _run_created_job(self, session: Session, job: Job) -> Job:
        runtime_config = self.runtime_settings.load()
        job.runtime_settings_json = runtime_config.model_dump_json()
        self._persist(job, session)
        self.storage.write_audit(
            job.id,
            "job_received",
            job.state,
            {"filename": job.original_filename, "desired_effect": job.desired_effect},
        )
        self.storage.write_audit(
            job.id,
            "runtime_settings_snapshot",
            job.state,
            self.runtime_settings.to_audit_payload(runtime_config),
        )
        self.storage.write_audit(
            job.id,
            "llm_execution_mode",
            job.state,
            self._llm_mode_audit_payload(runtime_config),
        )

        try:
            self._run_stage_a(job, session)
        except HTTPException:
            raise
        except Exception as exc:
            self._fail_job(job, session, str(exc))
            raise HTTPException(status_code=500, detail=f"Stage A failed: {exc}") from exc

        return self._refresh(session, job.id)

    def _resolve_adapter_output_path(self, adapter_result: dict[str, object]) -> Path | None:
        raw_path = adapter_result.get("output_path") if isinstance(adapter_result, dict) else None
        if not raw_path or not isinstance(raw_path, str):
            return None
        candidate = Path(raw_path)
        return candidate if candidate.exists() else None

    def _runtime_config_for_job(self, job: Job) -> RuntimeConfig:
        if job.runtime_settings_json:
            return RuntimeConfig.model_validate_json(job.runtime_settings_json)
        return self.runtime_settings.load()
