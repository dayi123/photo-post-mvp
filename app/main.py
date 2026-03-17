from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.config import get_settings
from app.db import get_session, init_db
from app.schemas import (
    ConfirmPlanRequest,
    CreateJobFromPathRequest,
    JobRead,
    JobState,
    Plan,
    ResultEnvelope,
    RuntimeConfigUpdate,
    RuntimeSettingsRead,
    SettingsTestResult,
)
from app.services.jobs import JobService
from app.services.runtime_settings import RuntimeSettingsService
from app.storage import StorageManager


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    RuntimeSettingsService(settings).load()
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="photo-post-mvp", lifespan=lifespan)
    service = JobService()
    runtime_settings = RuntimeSettingsService()
    storage = StorageManager()
    app_dir = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=str(app_dir / "templates"))
    app.mount("/static", StaticFiles(directory=app_dir / "static"), name="static")

    @app.get("/health")
    def healthcheck():
        return {"status": "ok"}

    @app.get("/ui", response_class=HTMLResponse)
    def ui_page(request: Request):
        return templates.TemplateResponse(request=request, name="ui.html", context={"request": request})

    @app.get("/settings", response_model=RuntimeSettingsRead)
    def get_runtime_settings():
        return runtime_settings.to_read(runtime_settings.load())

    @app.put("/settings", response_model=RuntimeSettingsRead)
    def update_runtime_settings(request: RuntimeConfigUpdate):
        return runtime_settings.to_read(runtime_settings.update(request))

    @app.post("/settings/test-llm", response_model=SettingsTestResult)
    def test_llm_settings():
        return runtime_settings.test_llm()

    @app.post("/settings/test-editor", response_model=SettingsTestResult)
    def test_editor_settings():
        return runtime_settings.test_editor()

    @app.post("/jobs", status_code=status.HTTP_201_CREATED, response_model=JobRead)
    def create_job(
        session: Annotated[Session, Depends(get_session)],
        file: UploadFile = File(...),
    ):
        job = service.create_job(session, file)
        return service.to_read(job)

    @app.post("/jobs/from-path", status_code=status.HTTP_201_CREATED, response_model=JobRead)
    def create_job_from_path(
        request: CreateJobFromPathRequest,
        session: Annotated[Session, Depends(get_session)],
    ):
        job = service.create_job_from_local_path(session, request.path)
        return service.to_read(job)

    @app.get("/jobs/{job_id}", response_model=JobRead)
    def get_job(job_id: str, session: Annotated[Session, Depends(get_session)]):
        return service.to_read(service.get_job(session, job_id))

    @app.get("/jobs/{job_id}/plan", response_model=Plan)
    def get_plan(job_id: str, session: Annotated[Session, Depends(get_session)]):
        return service.get_plan(session, job_id)

    @app.post("/jobs/{job_id}/confirm-plan", response_model=JobRead)
    def confirm_plan(
        job_id: str,
        request: ConfirmPlanRequest,
        session: Annotated[Session, Depends(get_session)],
    ):
        if not request.confirmed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plan confirmation was declined.")
        job = service.confirm_plan(session, job_id)
        return service.to_read(job)

    @app.post("/jobs/{job_id}/retry", response_model=JobRead)
    def retry_job(job_id: str, session: Annotated[Session, Depends(get_session)]):
        job = service.retry(session, job_id)
        return service.to_read(job)

    @app.get("/jobs/{job_id}/result")
    def get_result(job_id: str, session: Annotated[Session, Depends(get_session)]):
        job = service.get_job(session, job_id)
        if not job.final_path or job.state != JobState.DELIVERED_ARCHIVED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Final result is not ready yet.")
        final_path = Path(job.final_path)
        if not final_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Final file is missing.")
        return FileResponse(path=final_path, media_type="image/jpeg", filename=final_path.name)

    @app.get("/jobs/{job_id}/result/meta", response_model=ResultEnvelope)
    def get_result_meta(job_id: str, session: Annotated[Session, Depends(get_session)]):
        job = service.get_job(session, job_id)
        return ResultEnvelope(
            job=service.to_read(job),
            plan=service.get_plan(session, job_id) if job.plan_json else None,
            action=service.read_action(job),
            review=service.read_review(job),
            audit_files=storage.list_audits(job_id),
        )

    return app


app = create_app()
