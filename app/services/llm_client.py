from __future__ import annotations

import json
from typing import Any

import httpx

from app.schemas import Action, Plan, Review


class LlmClientError(RuntimeError):
    pass


class LlmClient:
    def __init__(self, timeout_seconds: int = 45) -> None:
        self.timeout = httpx.Timeout(timeout_seconds, connect=8.0)

    def generate_plan(self, request: dict[str, Any], provider: str) -> Plan:
        text = self._execute(request, provider)
        payload = self._extract_json(text)
        return Plan.model_validate(payload)

    def generate_action(self, request: dict[str, Any], provider: str) -> Action:
        text = self._execute(request, provider)
        payload = self._extract_json(text)
        return Action.model_validate(payload)

    def review_output(self, request: dict[str, Any], provider: str) -> Review:
        text = self._execute(request, provider)
        payload = self._extract_json(text)
        return Review.model_validate(payload)

    def _execute(self, request: dict[str, Any], provider: str) -> str:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.request(
                method=request["method"],
                url=request["url"],
                headers=request.get("headers"),
                params=request.get("params"),
                json=request.get("json"),
            )

            if (
                not response.is_success
                and provider in {"openai", "custom"}
                and str(request.get("url", "")).endswith("/responses")
                and response.status_code in {404, 405, 422, 500}
            ):
                fallback_request = self._build_chat_completions_fallback(request)
                response = client.request(
                    method=fallback_request["method"],
                    url=fallback_request["url"],
                    headers=fallback_request.get("headers"),
                    json=fallback_request.get("json"),
                )

        if not response.is_success:
            raise LlmClientError(f"LLM call failed: HTTP {response.status_code} {response.text[:400]}")

        if provider == "google":
            return self._extract_google_text(response)
        return self._extract_openai_text(response)

    @staticmethod
    def _extract_google_text(response: httpx.Response) -> str:
        body = response.json()
        candidates = body.get("candidates") or []
        if not candidates:
            raise LlmClientError("Google response has no candidates.")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        texts = [p.get("text") for p in parts if isinstance(p, dict) and p.get("text")]
        if not texts:
            raise LlmClientError("Google response has no text parts.")
        return "\n".join(texts)

    @staticmethod
    def _extract_openai_text(response: httpx.Response) -> str:
        body = response.json()

        # Responses API shape
        output = body.get("output")
        if isinstance(output, list):
            chunks: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                for content in item.get("content", []) or []:
                    if not isinstance(content, dict):
                        continue
                    text = content.get("text") or content.get("output_text")
                    if text:
                        chunks.append(text)
            if chunks:
                return "\n".join(chunks)

        # Chat Completions shape
        choices = body.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                chunks = [c.get("text") for c in content if isinstance(c, dict) and c.get("text")]
                if chunks:
                    return "\n".join(chunks)

        raise LlmClientError("Unable to extract text from OpenAI-compatible response.")

    @staticmethod
    def _build_chat_completions_fallback(request: dict[str, Any]) -> dict[str, Any]:
        url = str(request.get("url", ""))
        endpoint = url[: -len("/responses")] + "/chat/completions"
        body = request.get("json") or {}

        messages: list[dict[str, Any]] = []
        for item in body.get("input", []) or []:
            if not isinstance(item, dict):
                continue
            role = item.get("role", "user")
            content_parts = item.get("content", [])
            text_chunks: list[str] = []
            if isinstance(content_parts, list):
                for part in content_parts:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "input_text" and part.get("text"):
                        text_chunks.append(str(part["text"]))
                    elif part.get("type") == "input_image" and part.get("image_url"):
                        text_chunks.append(f"[image]{part['image_url']}")
            elif isinstance(content_parts, str):
                text_chunks.append(content_parts)
            messages.append({"role": role, "content": "\n".join(text_chunks).strip() or "ping"})

        return {
            "method": "POST",
            "url": endpoint,
            "headers": request.get("headers"),
            "json": {
                "model": body.get("model"),
                "messages": messages or [{"role": "user", "content": "ping"}],
                "max_tokens": min(int(body.get("max_output_tokens", 512)), 1024),
                "stream": False,
            },
        }

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()

        # Try direct parse first.
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Fallback: locate first JSON object in noisy output.
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise LlmClientError("Model output did not contain a JSON object.")
        candidate = stripped[start : end + 1]
        parsed = json.loads(candidate)
        if not isinstance(parsed, dict):
            raise LlmClientError("Model output JSON root must be an object.")
        return parsed
