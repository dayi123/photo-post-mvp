# photo-post-mvp

`photo-post-mvp` 是一个可直接运行的照片后期流程 MVP，基于 `FastAPI + Pydantic + SQLModel + SQLite + Uvicorn`。

当前版本包含：
- 照片上传、计划确认、结果下载的完整流程
- 本地 `stub` 的计划 / 动作 / 审核链路
- `stub` 与 `davinci` 两种编辑器后端
- 可在 Web UI 中修改的运行时设置
- 本地审计文件、运行时快照，以及两阶段提示词模板审计

## 项目说明

系统分为两个阶段：

1. Stage A：接收上传图片，导出 `preview_1`，生成结构化编辑计划，并进入人工确认状态。
2. Stage B：用户确认计划后，生成结构化编辑动作，交给当前配置的编辑器后端执行，导出 `preview_2`，进入 review loop，最终导出成片并归档。

核心模块：
- `app/main.py`：FastAPI 入口，提供 REST API 和 `/ui`
- `app/services/jobs.py`：任务编排、状态机、重试逻辑、审计写入
- `app/services/runtime_settings.py`：运行时设置读写、脱敏返回、连通性测试、模板请求骨架
- `app/services/prompt_templates.py`：模板 pack 选择、计划提示词渲染、动作提示词渲染、动作 JSON 合约摘要
- `app/services/llm_stub.py`：本地 plan / action / review stub
- `app/services/editor_adapters.py`：编辑器适配层，包含 `StubAdapter` 和 `DaVinciAdapter`
- `app/storage.py`：本地文件布局和审计文件写入

状态机：
- `RECEIVED`
- `PREVIEW_1_EXPORTED`
- `PLAN_GENERATED`
- `WAIT_USER_CONFIRM`
- `ACTION_GENERATED`
- `EDIT_APPLIED`
- `PREVIEW_2_EXPORTED`
- `QUALITY_CHECKED`
- `FINAL_EXPORTED`
- `DELIVERED_ARCHIVED`
- `FAILED`

## 存储布局

```text
data/runtime_config.json
data/jobs/{job_id}/original
data/jobs/{job_id}/preview_1.jpg
data/jobs/{job_id}/preview_2.jpg
data/jobs/{job_id}/final.jpg
data/jobs/{job_id}/audit/*.json
```

说明：
- `data/runtime_config.json` 保存当前运行时设置
- `audit` 目录保存关键阶段的结构化记录
- 每个新任务都会保存一份运行时设置快照到数据库，并把脱敏后的快照写入审计文件

## 快速开始

建议使用 Python 3.11+：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

默认访问地址：

```text
http://127.0.0.1:8000
```

## Web UI

启动服务后打开：

```text
http://127.0.0.1:8000/ui
```

页面包含两部分：

1. Settings：配置模型、API Key、Base URL、模板 pack 覆盖项、编辑器后端、DaVinci 命令与超时。
2. Job flow：上传照片、查看计划、确认计划、轮询状态、下载成片。

设置面板提供以下操作：
- `Save settings`
- `Test LLM`
- `Test Editor`
- `Reload settings`

模型预设：
- `gpt-5.4`
- `gemini-3.1`
- `custom`

模板 pack 覆盖项：
- `auto`
- `gpt-5.4`
- `gemini-3.1`
- `default`

UI 会在保存或重新加载后显示：
- `Effective plan pack`
- `Effective action pack`

## 模板 pack 行为

当前内置三个 pack：
- `gpt-5.4`
- `gemini-3.1`
- `default`

每个 pack 都包含两套模板：
- `plan` 阶段模板：只输出思路，不允许直接执行
- `action` 阶段模板：要求严格 JSON 输出，并附带动作 JSON 合约摘要

自动选择规则：
- 当 `plan_template_pack=auto` 时，根据 `llm_model` 自动选择计划模板 pack
- 当 `action_template_pack=auto` 时，根据 `llm_model` 自动选择动作模板 pack
- `llm_model` 包含 `gpt-5.4` 时，选中 `gpt-5.4`
- `llm_model` 包含 `gemini-3.1` 时，选中 `gemini-3.1`
- 其他模型回退到 `default`

覆盖规则：
- 只要 `plan_template_pack` 或 `action_template_pack` 不是 `auto`，就直接使用该值
- 计划阶段和动作阶段可以分别选择不同的 pack

## 运行时设置

运行时设置文件路径：

```text
data/runtime_config.json
```

示例：

```json
{
  "llm_provider": "openai",
  "llm_model": "gpt-5.4",
  "llm_api_key": null,
  "llm_base_url": null,
  "plan_template_pack": "auto",
  "action_template_pack": "auto",
  "editor_backend": "stub",
  "davinci_cmd": null,
  "davinci_input_mode": "stdin",
  "davinci_timeout_seconds": 60
}
```

字段说明：
- `llm_provider`：`openai | google | custom`
- `llm_model`：自由字符串，支持预设或手填
- `llm_api_key`：可选
- `llm_base_url`：可选，适用于第三方 relay 或兼容接口
- `plan_template_pack`：`auto | gpt-5.4 | gemini-3.1 | default`
- `action_template_pack`：`auto | gpt-5.4 | gemini-3.1 | default`
- `editor_backend`：`stub | davinci`
- `davinci_cmd`：DaVinci 外部命令，可选
- `davinci_input_mode`：`stdin | file`
- `davinci_timeout_seconds`：超时时间，单位秒

安全说明：
- `data/runtime_config.json` 会以明文形式保存在本地磁盘
- `/settings` 和审计文件不会返回完整 API Key，只保留脱敏后的值

## 审计与模板元数据

MVP 仍然使用本地 `stub` 生成计划和动作，但现在会把模板信息写入计划 / 动作审计，便于复现：

- 选中的 pack 名称
- 渲染后的完整提示词文本
- 动作阶段的 JSON 合约摘要

说明：
- 这些内容只用于审计和后续真实 LLM 接入准备
- 当前不会把 API Key 写入提示词或模板审计

## LLM 行为

当前版本为了保持 MVP 安全和确定性，任务执行中的计划生成、动作生成、审核仍然走本地 `stub`。

行为规则：
- 如果未配置 `llm_api_key`，系统继续使用本地 `stub`
- 如果已配置 `llm_api_key`，`/settings/test-llm` 可以测试连通性
- 即使已配置真实 LLM，任务主流程仍使用本地 `stub`，同时把模板选择和提示词写入审计

## 编辑器后端

默认情况下项目使用 `stub`，无需安装 DaVinci Resolve 也可以直接运行和测试。

当 `editor_backend=davinci` 时，Stage B 会把如下 JSON 载荷传给 `davinci_cmd`：

```json
{
  "round": 1,
  "action": {
    "profile": "social-natural-v1",
    "adjustments": [
      {
        "op": "exposure",
        "value": 12.0,
        "rationale": "lift subject visibility"
      }
    ],
    "export_format": "jpg"
  }
}
```

输入模式：
- `stdin`：JSON 直接写入标准输入
- `file`：JSON 写入临时文件，并通过环境变量 `PHOTO_POST_DAVINCI_PAYLOAD_PATH` 传给外部命令；如果命令中包含 `{payload_path}`，会自动替换为临时文件路径

示例：

```bash
set PHOTO_POST_EDITOR=davinci
set PHOTO_POST_DAVINCI_INPUT_MODE=stdin
set PHOTO_POST_DAVINCI_CMD=py -3 scripts\davinci_bridge.py --mode auto
```

```bash
set PHOTO_POST_EDITOR=davinci
set PHOTO_POST_DAVINCI_INPUT_MODE=file
set PHOTO_POST_DAVINCI_CMD=py -3 scripts\davinci_bridge.py --mode auto --payload "{payload_path}"
```

## API

### 任务接口

创建任务并上传图片：

```bash
curl -X POST "http://127.0.0.1:8000/jobs" ^
  -H "accept: application/json" ^
  -H "Content-Type: multipart/form-data" ^
  -F "file=@sample.jpg;type=image/jpeg"
```

查询任务状态：

```bash
curl "http://127.0.0.1:8000/jobs/<job_id>"
```

读取生成计划：

```bash
curl "http://127.0.0.1:8000/jobs/<job_id>/plan"
```

确认计划并继续执行：

```bash
curl -X POST "http://127.0.0.1:8000/jobs/<job_id>/confirm-plan" ^
  -H "Content-Type: application/json" ^
  -d "{\"confirmed\": true}"
```

失败后重试：

```bash
curl -X POST "http://127.0.0.1:8000/jobs/<job_id>/retry"
```

下载最终图片：

```bash
curl -L "http://127.0.0.1:8000/jobs/<job_id>/result" --output final.jpg
```

查看结果元数据和审计文件：

```bash
curl "http://127.0.0.1:8000/jobs/<job_id>/result/meta"
```

### 设置接口

读取当前设置：

```bash
curl "http://127.0.0.1:8000/settings"
```

更新设置：

```bash
curl -X PUT "http://127.0.0.1:8000/settings" ^
  -H "Content-Type: application/json" ^
  -d "{\"llm_provider\": \"openai\", \"llm_model\": \"gpt-5.4\", \"plan_template_pack\": \"auto\", \"action_template_pack\": \"auto\", \"editor_backend\": \"stub\"}"
```

测试 LLM 连通性：

```bash
curl -X POST "http://127.0.0.1:8000/settings/test-llm"
```

测试编辑器后端：

```bash
curl -X POST "http://127.0.0.1:8000/settings/test-editor"
```

`/settings` 返回的关键字段包括：
- `plan_template_pack`
- `action_template_pack`
- `effective_plan_template_pack`
- `effective_action_template_pack`

## 环境变量

可选环境变量：

```bash
set PHOTO_POST_DATABASE_URL=sqlite:///./photo_post_mvp.db
set PHOTO_POST_DATA_DIR=./data
set PHOTO_POST_MAX_REVIEW_ROUNDS=3
set PHOTO_POST_LLM_PROVIDER=openai
set PHOTO_POST_LLM_MODEL=gpt-5.4
set PHOTO_POST_LLM_API_KEY=
set PHOTO_POST_LLM_BASE_URL=
set PHOTO_POST_EDITOR=stub
set PHOTO_POST_DAVINCI_CMD=py -3 scripts\davinci_bridge.py --mode auto
set PHOTO_POST_DAVINCI_INPUT_MODE=stdin
set PHOTO_POST_DAVINCI_TIMEOUT_SECONDS=60
```

说明：
- 环境变量只作为 `runtime_config.json` 首次创建时的默认值来源
- 一旦运行时配置文件存在，后续以该文件内容为准

## 测试

运行：

```bash
pytest
```

当前测试覆盖：
- `/ui` 页面可访问
- 完整任务生命周期
- 运行时设置读写、脱敏与持久化
- 模板 pack 自动选择与提示词渲染
- 计划 / 动作审计中的模板元数据
- `test-editor` 在 `stub` 和 `davinci` 下的自测
- 审计文件不写入完整 API Key
- Schema 校验与状态机约束

## һ��������С�װ棩

����㲻���ֶ������ֱ���òֿ��Ŀ¼��һ���ű���

### ��ʽ 1��˫������������򵥣�

- ˫�� `quick_start.bat`
- �ű����Զ���
  - ��� Python
  - ���� `.venv`
  - ��װ����
  - ���������Զ��� `http://127.0.0.1:8000/ui`

### ��ʽ 2��PowerShell �ű����ɴ�������

```powershell
# ֻ��������װ������������
.\quick_setup.ps1 -SetupOnly

# ��װ��������Ĭ�ϴ��������
.\quick_setup.ps1

# ��װ�������������Զ��������
.\quick_setup.ps1 -NoBrowser
```

���� PowerShell ִ�в������ƣ������ڵ�ǰ�ն�ִ�У�

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```
