from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.schemas import Action, Plan, RuntimeConfig, RuntimeConfigUpdate, RuntimeSettingsRead, SettingsTestResult
from app.services.editor_adapters import EditorAdapterError, build_editor_adapter
from app.services import prompt_templates


LLM_TEST_TIMEOUT_SECONDS = 15


def mask_secret(secret: str | None) -> str | None:
    if not secret:
        return None
    trimmed = secret.strip()
    if not trimmed:
        return None
    tail_length = 4 if len(trimmed) > 4 else 1
    tail = trimmed[-tail_length:]
    return f"{'*' * max(4, len(trimmed) - tail_length)}{tail}"


class RuntimeSettingsService:
    def __init__(self, app_settings: Settings | None = None) -> None:
        self.app_settings = app_settings or get_settings()
        self.path = self.app_settings.runtime_config_path

    def load(self) -> RuntimeConfig:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            config = self.default_config()
            self._write(config)
            return config

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return RuntimeConfig.model_validate(raw)

    def update(self, patch: RuntimeConfigUpdate) -> RuntimeConfig:
        current = self.load()
        updates = patch.model_dump(exclude_unset=True)
        if "llm_api_key" in updates and updates["llm_api_key"] == "":
            updates["llm_api_key"] = None
        merged = current.model_dump()
        merged.update(updates)
        config = RuntimeConfig.model_validate(merged)
        self._write(config)
        return config

    def to_read(self, config: RuntimeConfig) -> RuntimeSettingsRead:
        return RuntimeSettingsRead(
            llm_provider=config.llm_provider,
            llm_model=config.llm_model,
            llm_api_key_masked=mask_secret(config.llm_api_key),
            llm_api_key_configured=bool(config.llm_api_key),
            llm_base_url=config.llm_base_url,
            plan_template_pack=config.plan_template_pack,
            action_template_pack=config.action_template_pack,
            effective_plan_template_pack=prompt_templates.resolve_pack(config.llm_model, config.plan_template_pack),
            effective_action_template_pack=prompt_templates.resolve_pack(config.llm_model, config.action_template_pack),
            editor_backend=config.editor_backend,
            davinci_cmd=config.davinci_cmd,
            davinci_input_mode=config.davinci_input_mode,
            davinci_timeout_seconds=config.davinci_timeout_seconds,
        )

    def to_audit_payload(self, config: RuntimeConfig) -> dict[str, Any]:
        return self.to_read(config).model_dump(mode="json")

    def llm_stub_audit_payload(self, config: RuntimeConfig) -> dict[str, Any]:
        if config.llm_api_key:
            note = (
                "LLM credentials are configured, but this MVP still uses the local stub for plan, action, and review."
            )
        else:
            note = "LLM API key is not configured. Using the local stub for plan, action, and review."

        return {
            "execution_backend": "stub",
            "configured_provider": config.llm_provider,
            "configured_model": config.llm_model,
            "llm_api_key_configured": bool(config.llm_api_key),
            "note": note,
        }

    def test_editor(self, config: RuntimeConfig | None = None) -> SettingsTestResult:
        runtime_config = config or self.load()

        # Keep settings test usable even when DaVinci backend is selected but not wired yet.
        effective_config = runtime_config
        if runtime_config.editor_backend == "davinci" and not runtime_config.davinci_cmd:
            effective_config = runtime_config.model_copy(update={"editor_backend": "stub"})

        adapter = build_editor_adapter(effective_config)
        sample_action = Action(
            profile="settings-self-test",
            adjustments=[{"op": "exposure", "value": 1, "rationale": "Connectivity self-test."}],
            export_format="jpg",
        )
        try:
            result = adapter.apply_action(sample_action, 0)
        except EditorAdapterError as exc:
            return SettingsTestResult(
                success=False,
                backend=runtime_config.editor_backend,
                message="Editor self-test failed.",
                detail=str(exc),
            )

        if runtime_config.editor_backend == "davinci" and not runtime_config.davinci_cmd:
            return SettingsTestResult(
                success=True,
                backend="stub",
                message="Editor self-test succeeded (stub fallback).",
                detail="DaVinci backend is selected but davinci_cmd is empty; configure davinci_cmd to test DaVinci directly.",
            )

        return SettingsTestResult(
            success=True,
            backend=runtime_config.editor_backend,
            message="Editor self-test succeeded.",
            detail=json.dumps(result, ensure_ascii=True),
        )

    def test_llm(self, config: RuntimeConfig | None = None) -> SettingsTestResult:
        runtime_config = config or self.load()
        if not runtime_config.llm_api_key:
            return SettingsTestResult(
                success=False,
                provider=runtime_config.llm_provider,
                model=runtime_config.llm_model,
                message="LLM API key is not configured.",
                detail="The MVP pipeline will continue using the local stub until a key is saved.",
            )

        try:
            request = self._build_llm_request(runtime_config)
            response = self._perform_llm_request(request)
            request_used = request
            should_fallback = (
                not response.is_success
                and runtime_config.llm_provider in {"openai", "custom"}
                and request["url"].endswith("/responses")
                and response.status_code in {404, 405, 422, 500}
            )
            if should_fallback:
                fallback_request = self._build_openai_chat_completions_request(runtime_config)
                fallback_response = self._perform_llm_request(fallback_request)
                if fallback_response.is_success:
                    response = fallback_response
                    request_used = fallback_request
        except httpx.HTTPError as exc:
            return SettingsTestResult(
                success=False,
                provider=runtime_config.llm_provider,
                model=runtime_config.llm_model,
                endpoint=None,
                message="LLM connectivity test failed.",
                detail=str(exc),
            )

        body_excerpt = self._truncate(response.text.strip())
        if response.is_success:
            return SettingsTestResult(
                success=True,
                provider=runtime_config.llm_provider,
                model=runtime_config.llm_model,
                endpoint=request_used["url"],
                status_code=response.status_code,
                message="LLM connectivity test succeeded.",
                detail=body_excerpt or "Received a successful response.",
            )

        return SettingsTestResult(
            success=False,
            provider=runtime_config.llm_provider,
            model=runtime_config.llm_model,
            endpoint=request_used["url"],
            status_code=response.status_code,
            message="LLM connectivity test failed.",
            detail=body_excerpt or "Remote service returned an error without a response body.",
        )

    def default_config(self) -> RuntimeConfig:
        return RuntimeConfig(
            llm_provider=self.app_settings.default_llm_provider,
            llm_model=self.app_settings.default_llm_model,
            llm_api_key=self.app_settings.default_llm_api_key,
            llm_base_url=self.app_settings.default_llm_base_url,
            plan_template_pack="auto",
            action_template_pack="auto",
            editor_backend=self.app_settings.default_editor_backend,
            davinci_cmd=self.app_settings.default_davinci_cmd,
            davinci_input_mode=self.app_settings.default_davinci_input_mode,
            davinci_timeout_seconds=self.app_settings.default_davinci_timeout_seconds,
        )

    def build_plan_request_payload(
        self,
        config: RuntimeConfig,
        original_filename: str,
        analysis_image_path: Path | None = None,
    ) -> dict[str, Any]:
        rendered = prompt_templates.build_plan_prompt(
            original_filename=original_filename,
            model=config.llm_model,
            override=config.plan_template_pack,
        )
        analysis_image_data = self._encode_image_as_data_url(analysis_image_path)
        return self._build_stage_request_payload(
            config,
            rendered.text,
            rendered.pack,
            analysis_image_data=analysis_image_data,
        )

    def build_action_request_payload(self, config: RuntimeConfig, plan: Plan, review_round: int) -> dict[str, Any]:
        rendered = prompt_templates.build_action_prompt(
            plan=plan,
            review_round=review_round,
            model=config.llm_model,
            override=config.action_template_pack,
        )
        return self._build_stage_request_payload(
            config,
            rendered.text,
            rendered.pack,
            contract_summary=rendered.contract_summary,
        )

    def build_review_request_payload(self, config: RuntimeConfig, review_round: int) -> dict[str, Any]:
        prompt = (
            "You are the quality review stage for a photo editing workflow. "
            "Return JSON only with keys: decision (approved|revise), approved (bool), "
            "score (0-100), notes (1-5 items), next_focus (string|null). "
            f"Current review_round: {review_round}."
        )
        return self._build_stage_request_payload(config, prompt, pack="default")

    def _write(self, config: RuntimeConfig) -> None:
        self.path.write_text(json.dumps(config.model_dump(mode="json"), indent=2), encoding="utf-8")

    def _build_stage_request_payload(
        self,
        config: RuntimeConfig,
        prompt_text: str,
        pack: str,
        contract_summary: dict[str, Any] | None = None,
        analysis_image_data: str | None = None,
    ) -> dict[str, Any]:
        if config.llm_provider == "google":
            parts: list[dict[str, Any]] = [{"text": prompt_text}]
            if analysis_image_data:
                mime, encoded = self._split_data_url(analysis_image_data)
                parts.append(
                    {
                        "inline_data": {
                            "mime_type": mime,
                            "data": encoded,
                        }
                    }
                )

            payload: dict[str, Any] = {
                "provider": config.llm_provider,
                "model": config.llm_model,
                "selected_pack": pack,
                "contents": [{"parts": parts}],
            }
            if contract_summary:
                payload["generationConfig"] = {
                    "responseMimeType": "application/json",
                    "schemaSummary": contract_summary,
                }
            return payload

        input_content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt_text}]
        if analysis_image_data:
            input_content.append(
                {
                    "type": "input_image",
                    "image_url": analysis_image_data,
                }
            )

        payload = {
            "provider": config.llm_provider,
            "model": config.llm_model,
            "selected_pack": pack,
            "input": [
                {
                    "role": "user",
                    "content": input_content,
                }
            ],
        }
        if contract_summary:
            payload["response_format"] = {
                "type": "json_schema_summary",
                "schema_summary": contract_summary,
            }
        return payload

    def _build_llm_request(self, config: RuntimeConfig) -> dict[str, Any]:
        if config.llm_provider == "google":
            return self._build_google_generate_content_request(
                config,
                [{"text": "ping"}],
                max_output_tokens=1,
            )

        return self._build_openai_responses_request(
            config,
            [{"type": "input_text", "text": "ping"}],
            max_output_tokens=1,
        )

    def build_llm_execute_request(self, config: RuntimeConfig, payload: dict[str, Any]) -> dict[str, Any]:
        if config.llm_provider == "google":
            return self._build_google_generate_content_request(
                config,
                payload["contents"][0]["parts"],
                max_output_tokens=512,
            )

        input_payload = payload.get("input")
        if isinstance(input_payload, list):
            normalized_input = input_payload[0].get("content", [])
        else:
            normalized_input = [{"type": "input_text", "text": str(input_payload or "")}]

        return self._build_openai_responses_request(
            config,
            normalized_input,
            max_output_tokens=1024,
        )

    def _build_openai_chat_completions_request(self, config: RuntimeConfig) -> dict[str, Any]:
        base_root = config.llm_base_url
        if config.llm_provider == "openai":
            base_root = base_root or "https://api.openai.com/v1"
        elif not base_root:
            raise httpx.RequestError("llm_base_url is required when llm_provider=custom.")

        base_url = self._join_base_url(base_root)
        endpoint = f"{base_url}/chat/completions"
        return {
            "method": "POST",
            "url": endpoint,
            "headers": {
                "Authorization": f"Bearer {config.llm_api_key}",
                "Content-Type": "application/json",
            },
            "json": {
                "model": config.llm_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            },
        }

    def _build_google_generate_content_request(
        self,
        config: RuntimeConfig,
        parts: list[dict[str, Any]],
        *,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        base_url = self._join_base_url(config.llm_base_url or "https://generativelanguage.googleapis.com/v1beta")
        model_name = config.llm_model if config.llm_model.startswith("models/") else f"models/{config.llm_model}"
        return {
            "method": "POST",
            "url": f"{base_url}/{model_name}:generateContent",
            "params": {"key": config.llm_api_key},
            "headers": {"Content-Type": "application/json"},
            "json": {
                "contents": [{"parts": parts}],
                "generationConfig": {"maxOutputTokens": max_output_tokens},
            },
        }

    def _build_openai_responses_request(
        self,
        config: RuntimeConfig,
        input_content: list[dict[str, Any]],
        *,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        base_root = config.llm_base_url
        if config.llm_provider == "openai":
            base_root = base_root or "https://api.openai.com/v1"
        elif not base_root:
            raise httpx.RequestError("llm_base_url is required when llm_provider=custom.")

        base_url = self._join_base_url(base_root)
        if base_url.endswith("/responses"):
            endpoint = base_url
        elif base_url.endswith("/chat/completions"):
            endpoint = base_url[: -len("/chat/completions")] + "/responses"
        else:
            endpoint = f"{base_url}/responses"

        return {
            "method": "POST",
            "url": endpoint,
            "headers": {
                "Authorization": f"Bearer {config.llm_api_key}",
                "Content-Type": "application/json",
            },
            "json": {
                "model": config.llm_model,
                "input": [
                    {
                        "role": "user",
                        "content": input_content,
                    }
                ],
                "max_output_tokens": max_output_tokens,
            },
        }

    def _perform_llm_request(self, request: dict[str, Any]) -> httpx.Response:
        timeout = httpx.Timeout(LLM_TEST_TIMEOUT_SECONDS, connect=5.0)
        with httpx.Client(timeout=timeout) as client:
            try:
                return client.request(
                    request["method"],
                    request["url"],
                    headers=request.get("headers"),
                    params=request.get("params"),
                    json=request.get("json"),
                )
            except httpx.ReadTimeout:
                # Retry once with a looser timeout because relay gateways can be bursty.
                retry_timeout = httpx.Timeout(LLM_TEST_TIMEOUT_SECONDS + 10, connect=5.0)
                return client.request(
                    request["method"],
                    request["url"],
                    headers=request.get("headers"),
                    params=request.get("params"),
                    json=request.get("json"),
                    timeout=retry_timeout,
                )

    @staticmethod
    def _encode_image_as_data_url(image_path: Path | None) -> str | None:
        if image_path is None or not image_path.exists():
            return None
        data = image_path.read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        mime = "image/jpeg"
        return f"data:{mime};base64,{encoded}"

    @staticmethod
    def _split_data_url(value: str) -> tuple[str, str]:
        if not value.startswith("data:") or "," not in value:
            raise ValueError("Invalid data URL.")
        header, encoded = value.split(",", 1)
        mime = header[5:].split(";", 1)[0] or "image/jpeg"
        return mime, encoded

    @staticmethod
    def _join_base_url(base_url: str) -> str:
        return base_url.rstrip("/")

    @staticmethod
    def _truncate(value: str, max_length: int = 240) -> str:
        if len(value) <= max_length:
            return value
        return f"{value[:max_length]}..."
