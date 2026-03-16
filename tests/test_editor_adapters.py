from __future__ import annotations

import sys
from pathlib import Path

from app.schemas import Action, RuntimeConfig
from app.services.editor_adapters import DaVinciAdapter, StubAdapter, build_editor_adapter


def test_default_editor_adapter_is_stub():
    adapter = build_editor_adapter(RuntimeConfig())
    assert isinstance(adapter, StubAdapter)


def test_davinci_editor_adapter_selected_by_runtime_config():
    adapter = build_editor_adapter(RuntimeConfig(editor_backend="davinci", davinci_cmd="python -V"))
    assert isinstance(adapter, DaVinciAdapter)


def test_davinci_adapter_reads_payload_from_stdin(tmp_path: Path):
    script_path = tmp_path / "davinci_echo.py"
    script_path.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "payload = json.load(sys.stdin)",
                "json.dump({'received_round': payload['round'], 'profile': payload['action']['profile']}, sys.stdout)",
            ]
        ),
        encoding="utf-8",
    )
    adapter = DaVinciAdapter(command=f'"{sys.executable}" "{script_path}"')
    action = Action(
        profile="clean-edit",
        adjustments=[{"op": "exposure", "value": 12, "rationale": "lift subject detail"}],
        export_format="jpg",
    )

    result = adapter.apply_action(action, 2)

    assert result["adapter"] == "davinci"
    assert result["output"]["received_round"] == 2
    assert result["output"]["profile"] == "clean-edit"
