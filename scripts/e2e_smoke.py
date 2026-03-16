from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.services.editor_adapters import get_editor_adapter


def main() -> int:
    # Small 1x1 png
    png = bytes.fromhex(
        "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
        "0000000D49444154789C6360F8CFC000000301010018DD8D180000000049454E44AE426082"
    )

    get_settings.cache_clear()
    get_editor_adapter.cache_clear()

    app = create_app()
    client = TestClient(app)

    create_resp = client.post("/jobs", files={"file": ("tiny.png", png, "image/png")})
    if create_resp.status_code != 201:
        print(f"create failed: {create_resp.status_code} {create_resp.text}")
        return 1

    job = create_resp.json()
    job_id = job["id"]
    print(f"job_id={job_id}")

    plan_resp = client.get(f"/jobs/{job_id}/plan")
    if plan_resp.status_code != 200:
        print(f"plan failed: {plan_resp.status_code} {plan_resp.text}")
        return 1

    confirm_resp = client.post(f"/jobs/{job_id}/confirm-plan", json={"confirmed": True})
    if confirm_resp.status_code != 200:
        print(f"confirm failed: {confirm_resp.status_code} {confirm_resp.text}")
        return 1

    state = confirm_resp.json().get("state")
    print(f"state_after_confirm={state}")

    result_resp = client.get(f"/jobs/{job_id}/result")
    if result_resp.status_code != 200:
        print(f"result failed: {result_resp.status_code} {result_resp.text}")
        return 1

    print("result_ready=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
