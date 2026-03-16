# CHANGELOG

## 2026-03-16

- Added model-specific prompt/template packs for `gpt-5.4`, `gemini-3.1`, and a `default` fallback.
- Added runtime-configurable `plan_template_pack` and `action_template_pack` settings with `auto` model-based resolution.
- Added `app/services/prompt_templates.py` for pack resolution, plan/action prompt rendering, and action JSON contract summaries.
- Added effective template-pack reporting to `/settings` and the Web UI settings panel.
- Added prompt-template metadata to plan/action audit records while keeping the MVP execution path on local stubs.
- Added runtime-settings helpers that build provider-specific plan/action request payload skeletons for future real LLM integration.
- Added tests for template resolution, template rendering, settings read/write coverage, and audit metadata.
- Added persistent runtime settings in `data/runtime_config.json`.
- Added `/settings`, `/settings/test-llm`, and `/settings/test-editor` APIs.
- Added API key masking for settings reads and audit-safe settings snapshots.
- Switched job execution to use a per-job runtime settings snapshot instead of a hardwired env-selected editor adapter.
- Kept the MVP job pipeline on local LLM stubs even when an LLM key is configured, with clear fallback notes in audits.
- Added a settings panel to `/ui` for provider, model, API key, base URL, editor backend, DaVinci command, input mode, and timeout.
- Added model presets for `gpt-5.4` and `gemini-3.1` while keeping free-form model input.
- Added tests for settings CRUD, persistence, masking, editor self-test, and audit secret redaction.
- Documented the new settings workflow and the MVP plain-text local key storage caveat in the README.
