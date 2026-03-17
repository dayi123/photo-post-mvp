from __future__ import annotations

import json
import sys
from pathlib import Path

from app.config import get_settings


def _read_audit_record(meta_payload: dict, kind: str) -> dict:
    for audit_path in meta_payload["audit_files"]:
        path = Path(audit_path)
        if path.name.endswith(f"_{kind}.json"):
            return json.loads(path.read_text(encoding="utf-8"))
    raise AssertionError(f"Audit record not found: {kind}")


def test_ui_route_exists(client):
    response = client.get("/ui")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Photo Post Console" in response.text


def test_job_lifecycle(client):
    response = client.post(
        "/jobs",
        files={"file": ("sample.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["state"] == "WAIT_USER_CONFIRM"
    job_id = payload["id"]

    plan_response = client.get(f"/jobs/{job_id}/plan")
    assert plan_response.status_code == 200
    assert plan_response.json()["steps"][0]["order"] == 1

    confirm_response = client.post(f"/jobs/{job_id}/confirm-plan", json={"confirmed": True})
    assert confirm_response.status_code == 200
    confirm_payload = confirm_response.json()
    assert confirm_payload["state"] == "DELIVERED_ARCHIVED"
    assert confirm_payload["review_rounds"] == 2

    result_meta = client.get(f"/jobs/{job_id}/result/meta")
    assert result_meta.status_code == 200
    meta_payload = result_meta.json()
    assert meta_payload["review"]["approved"] is True
    assert len(meta_payload["audit_files"]) >= 8

    analysis_audit = _read_audit_record(meta_payload, "analysis_input_exported")
    assert analysis_audit["payload"]["analysis_input_path"].endswith("analysis_input.jpg")
    assert analysis_audit["payload"]["bytes"] <= 5 * 1024 * 1024

    result_response = client.get(f"/jobs/{job_id}/result")
    assert result_response.status_code == 200
    assert result_response.content == b"fake-image-bytes"


def test_invalid_upload_type_is_rejected(client):
    response = client.post(
        "/jobs",
        files={"file": ("notes.txt", b"not-an-image", "text/plain")},
    )
    assert response.status_code == 400


def test_raw_upload_is_accepted_with_octet_stream(client):
    response = client.post(
        "/jobs",
        files={"file": ("sample.dng", b"fake-raw-bytes", "application/octet-stream")},
    )
    assert response.status_code == 201


def test_create_job_from_local_path(client, tmp_path: Path):
    photo = tmp_path / "local.jpg"
    photo.write_bytes(b"local-image-bytes")
    response = client.post("/jobs/from-path", json={"path": str(photo)})
    assert response.status_code == 201
    assert response.json()["original_filename"] == "local.jpg"


def test_large_upload_is_accepted_and_analysis_input_is_capped(client):
    payload = b"0" * (21 * 1024 * 1024)
    response = client.post(
        "/jobs",
        files={"file": ("big.jpg", payload, "image/jpeg")},
    )
    assert response.status_code == 201
    job_id = response.json()["id"]

    meta_payload = client.get(f"/jobs/{job_id}/result/meta").json()
    analysis_audit = _read_audit_record(meta_payload, "analysis_input_exported")
    assert analysis_audit["payload"]["bytes"] <= 5 * 1024 * 1024


def test_result_not_ready_before_confirmation(client):
    response = client.post(
        "/jobs",
        files={"file": ("sample.png", b"png-data", "image/png")},
    )
    job_id = response.json()["id"]

    result_response = client.get(f"/jobs/{job_id}/result")
    assert result_response.status_code == 409

    preview_1_path = Path(client.get(f"/jobs/{job_id}").json()["preview_1_path"])
    assert preview_1_path.exists()


def test_settings_crud_masks_key_and_persists(client):
    settings_path = get_settings().runtime_config_path

    initial_response = client.get("/settings")
    assert initial_response.status_code == 200
    assert settings_path.exists()
    assert initial_response.json()["llm_api_key_masked"] is None
    assert initial_response.json()["plan_template_pack"] == "auto"
    assert initial_response.json()["action_template_pack"] == "auto"
    assert initial_response.json()["effective_plan_template_pack"] == "gemini-3.1"
    assert initial_response.json()["effective_action_template_pack"] == "gemini-3.1"

    update_payload = {
        "llm_provider": "custom",
        "llm_model": "relay-model",
        "llm_api_key": "sk-test-123456",
        "llm_base_url": "https://relay.example.test/v1",
        "plan_template_pack": "gemini-3.1",
        "action_template_pack": "default",
        "editor_backend": "stub",
        "davinci_cmd": "",
        "davinci_input_mode": "stdin",
        "davinci_timeout_seconds": 45,
    }
    update_response = client.put("/settings", json=update_payload)
    assert update_response.status_code == 200
    update_json = update_response.json()
    assert update_json["llm_api_key_configured"] is True
    assert update_json["llm_api_key_masked"].endswith("3456")
    assert update_json["plan_template_pack"] == "gemini-3.1"
    assert update_json["action_template_pack"] == "default"
    assert update_json["effective_plan_template_pack"] == "gemini-3.1"
    assert update_json["effective_action_template_pack"] == "default"
    assert "sk-test-123456" not in update_response.text

    stored = json.loads(settings_path.read_text(encoding="utf-8"))
    assert stored["llm_api_key"] == "sk-test-123456"
    assert stored["llm_base_url"] == "https://relay.example.test/v1"
    assert stored["plan_template_pack"] == "gemini-3.1"
    assert stored["action_template_pack"] == "default"

    follow_up_response = client.put("/settings", json={"llm_model": "relay-model-v2"})
    assert follow_up_response.status_code == 200
    follow_up_json = follow_up_response.json()
    assert follow_up_json["llm_model"] == "relay-model-v2"
    assert follow_up_json["llm_api_key_masked"].endswith("3456")
    assert follow_up_json["effective_plan_template_pack"] == "gemini-3.1"
    assert follow_up_json["effective_action_template_pack"] == "default"

    clear_key_response = client.put("/settings", json={"llm_api_key": ""})
    assert clear_key_response.status_code == 200
    clear_key_json = clear_key_response.json()
    assert clear_key_json["llm_api_key_configured"] is False
    assert clear_key_json["llm_api_key_masked"] is None

    reloaded = json.loads(settings_path.read_text(encoding="utf-8"))
    assert reloaded["llm_api_key"] is None
    assert reloaded["llm_model"] == "relay-model-v2"


def test_settings_test_llm_without_key_reports_stub_fallback(client):
    response = client.post("/settings/test-llm")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert "stub" in payload["detail"].lower()


def test_settings_test_editor_supports_stub_and_davinci(client, tmp_path: Path):
    stub_response = client.post("/settings/test-editor")
    assert stub_response.status_code == 200
    assert stub_response.json()["success"] is True
    assert stub_response.json()["backend"] == "stub"

    fallback_response = client.put(
        "/settings",
        json={
            "editor_backend": "davinci",
            "davinci_cmd": "",
            "davinci_input_mode": "stdin",
            "davinci_timeout_seconds": 10,
        },
    )
    assert fallback_response.status_code == 200
    fallback_test = client.post("/settings/test-editor")
    assert fallback_test.status_code == 200
    assert fallback_test.json()["success"] is True
    assert fallback_test.json()["backend"] == "stub"

    script_path = tmp_path / "davinci_self_test.py"
    script_path.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "payload = json.load(sys.stdin)",
                "json.dump({'ok': True, 'round': payload['round']}, sys.stdout)",
            ]
        ),
        encoding="utf-8",
    )
    update_response = client.put(
        "/settings",
        json={
            "editor_backend": "davinci",
            "davinci_cmd": f'"{sys.executable}" "{script_path}"',
            "davinci_input_mode": "stdin",
            "davinci_timeout_seconds": 10,
        },
    )
    assert update_response.status_code == 200

    davinci_response = client.post("/settings/test-editor")
    assert davinci_response.status_code == 200
    davinci_payload = davinci_response.json()
    assert davinci_payload["success"] is True
    assert davinci_payload["backend"] == "davinci"
    assert '"round": 0' in davinci_payload["detail"]


def test_retry_uses_latest_runtime_settings(client, tmp_path: Path):
    bad_settings = client.put(
        "/settings",
        json={
            "editor_backend": "davinci",
            "davinci_cmd": "",
            "davinci_input_mode": "stdin",
            "davinci_timeout_seconds": 10,
        },
    )
    assert bad_settings.status_code == 200

    created = client.post(
        "/jobs",
        files={"file": ("sample.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert created.status_code == 201
    job_id = created.json()["id"]

    failed = client.post(f"/jobs/{job_id}/confirm-plan", json={"confirmed": True})
    assert failed.status_code == 500

    script_path = tmp_path / "davinci_retry.py"
    script_path.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "payload = json.load(sys.stdin)",
                "json.dump({'output_path': None, 'round': payload['round']}, sys.stdout)",
            ]
        ),
        encoding="utf-8",
    )

    good_settings = client.put(
        "/settings",
        json={
            "editor_backend": "davinci",
            "davinci_cmd": f'\"{sys.executable}\" \"{script_path}\"',
            "davinci_input_mode": "stdin",
            "davinci_timeout_seconds": 10,
        },
    )
    assert good_settings.status_code == 200

    retry = client.post(f"/jobs/{job_id}/retry")
    assert retry.status_code == 200
    assert retry.json()["state"] in {"FAILED", "DELIVERED_ARCHIVED"}

    meta_payload = client.get(f"/jobs/{job_id}/result/meta").json()
    snapshot_retry = _read_audit_record(meta_payload, "runtime_settings_snapshot_retry")
    assert "davinci_retry.py" in (snapshot_retry["payload"].get("davinci_cmd") or "")


def test_job_audit_settings_snapshot_masks_api_key(client):
    client.put(
        "/settings",
        json={
            "llm_provider": "openai",
            "llm_model": "gemini-3.1-pro-preview",
            "llm_api_key": "sk-live-987654",
        },
    )

    response = client.post(
        "/jobs",
        files={"file": ("sample.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    job_id = response.json()["id"]
    meta = client.get(f"/jobs/{job_id}/result/meta").json()

    audit_text = "\n".join(Path(path).read_text(encoding="utf-8") for path in meta["audit_files"])
    assert "sk-live-987654" not in audit_text
    assert "llm_api_key_masked" in audit_text
    assert "7654" in audit_text


def test_plan_and_action_audits_include_template_metadata(client):
    client.put(
        "/settings",
        json={
            "llm_provider": "google",
            "llm_model": "models/gemini-3.1-pro",
            "plan_template_pack": "auto",
            "action_template_pack": "default",
        },
    )

    response = client.post(
        "/jobs",
        files={"file": ("sample.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    job_id = response.json()["id"]
    client.post(f"/jobs/{job_id}/confirm-plan", json={"confirmed": True})

    meta = client.get(f"/jobs/{job_id}/result/meta").json()
    plan_audit = _read_audit_record(meta, "plan_generated")
    action_audit = _read_audit_record(meta, "action_generated_round_1")

    assert plan_audit["payload"]["prompt_template"]["selected_pack"] == "gemini-3.1"
    assert "Input filename: sample.jpg" in plan_audit["payload"]["prompt_template"]["rendered_prompt"]
    prepared_payload = plan_audit["payload"]["prepared_request_payload"]
    parts = prepared_payload["contents"][0]["parts"]
    assert any("inline_data" in part for part in parts)
    assert action_audit["payload"]["prompt_template"]["selected_pack"] == "default"
    assert "Output JSON only and follow the contract exactly." in action_audit["payload"]["prompt_template"]["rendered_prompt"]
    assert action_audit["payload"]["prompt_template"]["json_schema_contract_summary"]["required"] == [
        "profile",
        "adjustments",
        "export_format",
    ]
