const state = {
  jobId: null,
  pollTimer: null,
  language: "en",
};

const MODEL_PRESETS = [
  "gemini-3.1-pro-preview",
  "gemini-3-pro-preview",
  "gpt-5.4",
  "gemini-3.1",
];
const TAB_IDS = ["workbench", "settings"];

const I18N = {
  en: {
    page_title: "Photo Post MVP Console",
    hero_title: "Photo Post Console",
    hero_subtitle: "Upload, confirm plan, and export final image. Switch language anytime.",
    label_language: "Language",
    tab_workbench: "Workbench",
    tab_settings: "Settings",
    label_photo: "Photo",
    btn_upload: "Upload photo",
    btn_retry: "Retry",
    job_status_title: "Job status",
    job_status_subtitle: "The pipeline starts with plan generation and waits for confirmation.",
    field_job_id: "Job ID",
    field_filename: "Filename",
    field_review_rounds: "Review rounds",
    field_error: "Error",
    btn_confirm_plan: "Confirm plan",
    plan_title: "Generated plan",
    plan_subtitle: "This appears after the initial upload finishes.",
    plan_empty: "No plan yet.",
    plan_goals: "Goals",
    plan_risks: "Risks",
    plan_steps: "Steps",
    result_title: "Final image",
    result_subtitle: "Once delivered, the final image appears here.",
    result_empty: "No final image yet.",
    btn_download: "Download final image",
    settings_title: "Settings",
    settings_subtitle: "Configure model, relay base URL, and editor backend for new jobs.",
    field_provider: "Provider",
    field_model_preset: "Model preset",
    option_custom: "Custom",
    field_model: "Model",
    field_api_key: "API key",
    field_base_url: "Base URL",
    field_plan_pack: "Plan template pack",
    field_action_pack: "Action template pack",
    field_editor_backend: "Editor backend",
    field_davinci_cmd: "DaVinci command",
    field_input_mode: "Input mode",
    field_timeout: "Timeout (seconds)",
    field_current_key: "Current key",
    field_status: "Status",
    field_effective_plan: "Effective plan pack",
    field_effective_action: "Effective action pack",
    btn_save: "Save settings",
    btn_test_llm: "Test LLM",
    btn_test_editor: "Test Editor",
    btn_reload: "Reload settings",
    settings_test_placeholder: "No settings test has been run yet.",

    prompt_choose_photo: "Choose a photo first.",
    prompt_uploading: "Uploading photo and generating plan...",
    prompt_plan_ready: "Plan ready. Review it and confirm when ready.",
    prompt_confirming: "Plan confirmed. Running editor flow...",
    prompt_retrying: "Retry started. Re-running pipeline...",
    prompt_failed_retry_hint: "Job failed. Click Retry to run it again.",
    prompt_file_too_large: "File is too large. Please keep it under 20MB.",
    prompt_final_ready: "Final image is ready.",

    settings_loading: "Settings loaded.",
    settings_saving: "Saving settings...",
    settings_saved: "Settings saved.",
    settings_saved_hint: "Settings saved. Run a test to verify connectivity.",
    settings_reloaded: "Settings reloaded.",
    settings_llm_running: "LLM test running...",
    settings_editor_running: "Editor test running...",
    status_not_loaded: "Not loaded",
    status_key_configured: "Key configured",
    status_stub_fallback: "Stub fallback",
    not_set: "Not set",
    no_major_risks: "No major risks identified.",
    estimated_minutes: "Estimated time",
    unit_minutes: "minutes",
    idle: "Idle",
  },
  zh: {
    page_title: "Photo Post MVP 控制台",
    hero_title: "照片后期控制台",
    hero_subtitle: "上传照片、确认方案、导出成片。支持中英文切换。",
    label_language: "语言",
    tab_workbench: "工作台",
    tab_settings: "配置",
    label_photo: "照片",
    btn_upload: "上传照片",
    btn_retry: "重试",
    job_status_title: "任务状态",
    job_status_subtitle: "流程先生成调整方案，再等待你确认。",
    field_job_id: "任务 ID",
    field_filename: "文件名",
    field_review_rounds: "复检轮次",
    field_error: "错误",
    btn_confirm_plan: "确认方案",
    plan_title: "生成的调整方案",
    plan_subtitle: "上传完成后会显示在这里。",
    plan_empty: "暂无方案。",
    plan_goals: "目标",
    plan_risks: "风险",
    plan_steps: "步骤",
    result_title: "最终成片",
    result_subtitle: "任务完成后，成片会显示在这里。",
    result_empty: "暂无成片。",
    btn_download: "下载最终图片",
    settings_title: "配置",
    settings_subtitle: "配置模型、中转地址、编辑器后端等参数。",
    field_provider: "服务提供方",
    field_model_preset: "模型预设",
    option_custom: "自定义",
    field_model: "模型名称",
    field_api_key: "API Key",
    field_base_url: "Base URL",
    field_plan_pack: "思路模板包",
    field_action_pack: "执行模板包",
    field_editor_backend: "编辑器后端",
    field_davinci_cmd: "DaVinci 命令",
    field_input_mode: "输入模式",
    field_timeout: "超时（秒）",
    field_current_key: "当前 Key",
    field_status: "状态",
    field_effective_plan: "生效思路模板",
    field_effective_action: "生效执行模板",
    btn_save: "保存配置",
    btn_test_llm: "测试 LLM",
    btn_test_editor: "测试编辑器",
    btn_reload: "重新加载",
    settings_test_placeholder: "尚未进行配置测试。",

    prompt_choose_photo: "请先选择一张照片。",
    prompt_uploading: "正在上传并生成方案...",
    prompt_plan_ready: "方案已生成，请确认后继续。",
    prompt_confirming: "方案已确认，正在执行处理流程...",
    prompt_retrying: "已开始重试，正在重新执行流程...",
    prompt_failed_retry_hint: "任务失败，可点击重试再次运行。",
    prompt_file_too_large: "文件过大，请控制在 20MB 以内。",
    prompt_final_ready: "最终图片已生成。",

    settings_loading: "配置已加载。",
    settings_saving: "正在保存配置...",
    settings_saved: "配置已保存。",
    settings_saved_hint: "配置已保存，可点击测试检查连通性。",
    settings_reloaded: "配置已重新加载。",
    settings_llm_running: "正在测试 LLM...",
    settings_editor_running: "正在测试编辑器...",
    status_not_loaded: "未加载",
    status_key_configured: "Key 已配置",
    status_stub_fallback: "使用本地 stub",
    not_set: "未设置",
    no_major_risks: "未识别明显风险。",
    estimated_minutes: "预计耗时",
    unit_minutes: "分钟",
    idle: "空闲",
  },
};

const settingsForm = document.getElementById("settings-form");
const settingsProvider = document.getElementById("settings-provider");
const settingsModelPreset = document.getElementById("settings-model-preset");
const settingsModelInput = document.getElementById("settings-model-input");
const settingsApiKey = document.getElementById("settings-api-key");
const settingsBaseUrl = document.getElementById("settings-base-url");
const settingsPlanTemplatePack = document.getElementById("settings-plan-template-pack");
const settingsActionTemplatePack = document.getElementById("settings-action-template-pack");
const settingsEditorBackend = document.getElementById("settings-editor-backend");
const settingsDavinciCmd = document.getElementById("settings-davinci-cmd");
const settingsDavinciInputMode = document.getElementById("settings-davinci-input-mode");
const settingsDavinciTimeout = document.getElementById("settings-davinci-timeout");
const settingsKeyMask = document.getElementById("settings-key-mask");
const settingsStatus = document.getElementById("settings-status");
const settingsEffectivePlanPack = document.getElementById("settings-effective-plan-pack");
const settingsEffectiveActionPack = document.getElementById("settings-effective-action-pack");
const settingsFlash = document.getElementById("settings-flash");
const settingsTestResult = document.getElementById("settings-test-result");
const settingsSaveButton = document.getElementById("settings-save-button");
const settingsTestLlmButton = document.getElementById("settings-test-llm-button");
const settingsTestEditorButton = document.getElementById("settings-test-editor-button");
const settingsReloadButton = document.getElementById("settings-reload-button");

const languageSelect = document.getElementById("language-select");
const tabWorkbench = document.getElementById("tab-workbench");
const tabSettings = document.getElementById("tab-settings");
const panelWorkbench = document.getElementById("panel-workbench");
const panelSettings = document.getElementById("panel-settings");

const uploadForm = document.getElementById("upload-form");
const photoInput = document.getElementById("photo-input");
const uploadButton = document.getElementById("upload-button");
const confirmButton = document.getElementById("confirm-button");
const retryButton = document.getElementById("retry-button");
const flash = document.getElementById("flash");
const jobState = document.getElementById("job-state");
const jobId = document.getElementById("job-id");
const jobFile = document.getElementById("job-file");
const jobRounds = document.getElementById("job-rounds");
const jobError = document.getElementById("job-error");
const planEmpty = document.getElementById("plan-empty");
const planContent = document.getElementById("plan-content");
const planSummary = document.getElementById("plan-summary");
const planGoals = document.getElementById("plan-goals");
const planRisks = document.getElementById("plan-risks");
const planSteps = document.getElementById("plan-steps");
const resultEmpty = document.getElementById("result-empty");
const resultContent = document.getElementById("result-content");
const resultImage = document.getElementById("result-image");
const resultDownload = document.getElementById("result-download");

function t(key) {
  const lang = I18N[state.language] ? state.language : "en";
  return I18N[lang][key] || I18N.en[key] || key;
}

function applyTranslations() {
  document.documentElement.lang = state.language;
  for (const node of document.querySelectorAll("[data-i18n]")) {
    const key = node.dataset.i18n;
    node.textContent = t(key);
  }

  document.title = t("page_title");
  if (!jobState.textContent || jobState.textContent === I18N.en.idle || jobState.textContent === I18N.zh.idle) {
    jobState.textContent = t("idle");
  }
  if (planEmpty.hidden === false) {
    planEmpty.textContent = t("plan_empty");
  }
  if (resultEmpty.hidden === false) {
    resultEmpty.textContent = t("result_empty");
  }
  if (!settingsTestResult.dataset.custom) {
    settingsTestResult.textContent = t("settings_test_placeholder");
  }
}

function setLanguage(lang) {
  state.language = lang === "zh" ? "zh" : "en";
  window.localStorage.setItem("pp_lang", state.language);
  if (languageSelect.value !== state.language) {
    languageSelect.value = state.language;
  }
  applyTranslations();
}

function activateTab(tabId) {
  const normalized = TAB_IDS.includes(tabId) ? tabId : "workbench";
  tabWorkbench.classList.toggle("active", normalized === "workbench");
  tabSettings.classList.toggle("active", normalized === "settings");

  panelWorkbench.classList.toggle("active", normalized === "workbench");
  panelSettings.classList.toggle("active", normalized === "settings");
  panelWorkbench.hidden = normalized !== "workbench";
  panelSettings.hidden = normalized !== "settings";
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail || JSON.stringify(payload);
    } catch (error) {
      detail = await response.text();
    }
    throw new Error(detail || "Request failed.");
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response;
}

function setFlash(message, isError = false) {
  flash.textContent = message;
  flash.style.color = isError ? "var(--danger)" : "var(--muted)";
}

function setSettingsFlash(message, isError = false) {
  settingsFlash.textContent = message;
  settingsFlash.style.color = isError ? "var(--danger)" : "var(--muted)";
}

function setSettingsTestResult(result, isError = false) {
  settingsTestResult.textContent = result;
  settingsTestResult.classList.toggle("error", isError);
  settingsTestResult.dataset.custom = "1";
}

function renderList(container, items, formatter = (item) => item) {
  container.replaceChildren();
  for (const item of items) {
    const element = document.createElement("li");
    element.textContent = formatter(item);
    container.appendChild(element);
  }
}

function renderPlan(plan) {
  if (!plan) {
    planEmpty.hidden = false;
    planContent.hidden = true;
    planEmpty.textContent = t("plan_empty");
    return;
  }

  planEmpty.hidden = true;
  planContent.hidden = false;
  planSummary.textContent = `${plan.summary} ${t("estimated_minutes")}: ${plan.estimated_minutes} ${t("unit_minutes")}.`;
  renderList(planGoals, plan.goals);
  renderList(planRisks, plan.risks.length ? plan.risks : [t("no_major_risks")]);
  renderList(planSteps, plan.steps, (step) => `${step.title}: ${step.instruction}`);
}

function renderJob(job) {
  jobState.textContent = job.state;
  jobState.className = "badge";
  if (job.state === "DELIVERED_ARCHIVED") {
    jobState.classList.add("ready");
  } else if (job.state === "FAILED") {
    jobState.classList.add("failed");
  }

  jobId.textContent = job.id;
  jobFile.textContent = job.original_filename;
  jobRounds.textContent = String(job.review_rounds);
  jobError.textContent = job.error_message || "-";

  const canConfirm = job.state === "WAIT_USER_CONFIRM";
  const canRetry = job.state === "FAILED";
  confirmButton.hidden = !canConfirm;
  confirmButton.disabled = !canConfirm;
  retryButton.hidden = !canRetry;
  retryButton.disabled = !canRetry;
}

function showResult(job) {
  if (!job.result_ready) {
    resultEmpty.hidden = false;
    resultContent.hidden = true;
    resultEmpty.textContent = t("result_empty");
    return;
  }

  const imageUrl = `/jobs/${job.id}/result?ts=${Date.now()}`;
  resultImage.src = imageUrl;
  resultDownload.href = `/jobs/${job.id}/result`;
  resultDownload.download = `${job.id}-final.jpg`;
  resultEmpty.hidden = true;
  resultContent.hidden = false;
}

function stopPolling() {
  if (state.pollTimer) {
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

function syncModelControls(model) {
  if (MODEL_PRESETS.includes(model)) {
    settingsModelPreset.value = model;
  } else {
    settingsModelPreset.value = "custom";
  }
  settingsModelInput.value = model;
  settingsModelInput.disabled = settingsModelPreset.value !== "custom";
}

function toggleEditorFields() {
  const davinciSelected = settingsEditorBackend.value === "davinci";
  settingsDavinciCmd.disabled = !davinciSelected;
  settingsDavinciInputMode.disabled = !davinciSelected;
  settingsDavinciTimeout.disabled = !davinciSelected;
}

function collectSettingsPayload() {
  const model =
    settingsModelPreset.value === "custom" ? settingsModelInput.value.trim() : settingsModelPreset.value;
  const payload = {
    llm_provider: settingsProvider.value,
    llm_model: model,
    llm_base_url: settingsBaseUrl.value.trim(),
    plan_template_pack: settingsPlanTemplatePack.value,
    action_template_pack: settingsActionTemplatePack.value,
    editor_backend: settingsEditorBackend.value,
    davinci_cmd: settingsDavinciCmd.value.trim(),
    davinci_input_mode: settingsDavinciInputMode.value,
    davinci_timeout_seconds: Number(settingsDavinciTimeout.value || 60),
  };
  // Always send llm_api_key so users can explicitly clear a saved key from the UI.
  payload.llm_api_key = settingsApiKey.value.trim();
  return payload;
}

function renderSettings(settings) {
  settingsProvider.value = settings.llm_provider;
  syncModelControls(settings.llm_model);
  settingsApiKey.value = "";
  settingsBaseUrl.value = settings.llm_base_url || "";
  settingsPlanTemplatePack.value = settings.plan_template_pack;
  settingsActionTemplatePack.value = settings.action_template_pack;
  settingsEditorBackend.value = settings.editor_backend;
  settingsDavinciCmd.value = settings.davinci_cmd || "";
  settingsDavinciInputMode.value = settings.davinci_input_mode;
  settingsDavinciTimeout.value = String(settings.davinci_timeout_seconds);
  settingsKeyMask.textContent = settings.llm_api_key_masked || t("not_set");
  settingsStatus.textContent = settings.llm_api_key_configured ? t("status_key_configured") : t("status_stub_fallback");
  settingsEffectivePlanPack.textContent = settings.effective_plan_template_pack;
  settingsEffectiveActionPack.textContent = settings.effective_action_template_pack;
  toggleEditorFields();
}

async function loadSettings(message = t("settings_loading")) {
  const settings = await api("/settings");
  renderSettings(settings);
  setSettingsFlash(message);
}

async function runSettingsTest(path, button, labelText) {
  button.disabled = true;
  setSettingsFlash(labelText);
  try {
    const result = await api(path, { method: "POST" });
    setSettingsTestResult(
      [result.message, result.detail, result.status_code ? `HTTP ${result.status_code}` : null]
        .filter(Boolean)
        .join(" "),
      !result.success,
    );
    setSettingsFlash(result.message, !result.success);
  } catch (error) {
    setSettingsTestResult(error.message, true);
    setSettingsFlash(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function refreshJob() {
  if (!state.jobId) {
    return;
  }

  const job = await api(`/jobs/${state.jobId}`);
  renderJob(job);
  showResult(job);
  if (job.state === "DELIVERED_ARCHIVED") {
    stopPolling();
    setFlash(t("prompt_final_ready"));
  } else if (job.state === "FAILED") {
    stopPolling();
    setFlash(t("prompt_failed_retry_hint"), true);
  }
}

function startPolling() {
  stopPolling();
  state.pollTimer = window.setInterval(() => {
    refreshJob().catch((error) => {
      stopPolling();
      setFlash(error.message, true);
    });
  }, 1500);
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = photoInput.files[0];
  if (!file) {
    setFlash(t("prompt_choose_photo"), true);
    return;
  }

  const maxBytes = 20 * 1024 * 1024;
  if (file.size > maxBytes) {
    setFlash(`${t("prompt_file_too_large")} (${(file.size / 1024 / 1024).toFixed(1)}MB)`, true);
    return;
  }

  stopPolling();
  uploadButton.disabled = true;
  confirmButton.hidden = true;
  confirmButton.disabled = true;
  retryButton.hidden = true;
  retryButton.disabled = true;
  renderPlan(null);
  showResult({ result_ready: false });
  setFlash(t("prompt_uploading"));

  try {
    const formData = new FormData();
    formData.append("file", file);
    const job = await api("/jobs", { method: "POST", body: formData });
    state.jobId = job.id;
    renderJob(job);
    showResult(job);
    const plan = await api(`/jobs/${job.id}/plan`);
    renderPlan(plan);
    setFlash(t("prompt_plan_ready"));
  } catch (error) {
    setFlash(error.message, true);
  } finally {
    uploadButton.disabled = false;
  }
});

confirmButton.addEventListener("click", async () => {
  if (!state.jobId) {
    return;
  }

  confirmButton.disabled = true;
  setFlash(t("prompt_confirming"));

  try {
    const job = await api(`/jobs/${state.jobId}/confirm-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmed: true }),
    });
    renderJob(job);
    showResult(job);
    if (job.result_ready || job.state === "FAILED") {
      setFlash(job.result_ready ? t("prompt_final_ready") : job.error_message || "Job failed.", job.state === "FAILED");
      return;
    }
    startPolling();
  } catch (error) {
    confirmButton.disabled = false;
    if (error.message.includes("cannot confirm plan") || error.message.includes("FAILED")) {
      setFlash(t("prompt_failed_retry_hint"), true);
      await refreshJob();
      return;
    }
    setFlash(error.message, true);
  }
});

retryButton.addEventListener("click", async () => {
  if (!state.jobId) {
    return;
  }

  retryButton.disabled = true;
  setFlash(t("prompt_retrying"));
  try {
    const job = await api(`/jobs/${state.jobId}/retry`, { method: "POST" });
    renderJob(job);
    showResult(job);

    if (job.state === "WAIT_USER_CONFIRM") {
      const plan = await api(`/jobs/${job.id}/plan`);
      renderPlan(plan);
      setFlash(t("prompt_plan_ready"));
      return;
    }

    if (job.result_ready) {
      setFlash(t("prompt_final_ready"));
      return;
    }

    startPolling();
  } catch (error) {
    retryButton.disabled = false;
    setFlash(error.message, true);
  }
});

settingsModelPreset.addEventListener("change", () => {
  if (settingsModelPreset.value !== "custom") {
    settingsModelInput.value = settingsModelPreset.value;
  }
  settingsModelInput.disabled = settingsModelPreset.value !== "custom";
});

settingsEditorBackend.addEventListener("change", toggleEditorFields);

settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  settingsSaveButton.disabled = true;
  setSettingsFlash(t("settings_saving"));

  try {
    const settings = await api("/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectSettingsPayload()),
    });
    renderSettings(settings);
    setSettingsFlash(t("settings_saved"));
    setSettingsTestResult(t("settings_saved_hint"));
  } catch (error) {
    setSettingsFlash(error.message, true);
  } finally {
    settingsSaveButton.disabled = false;
  }
});

settingsTestLlmButton.addEventListener("click", async () => {
  await runSettingsTest("/settings/test-llm", settingsTestLlmButton, t("settings_llm_running"));
});

settingsTestEditorButton.addEventListener("click", async () => {
  await runSettingsTest("/settings/test-editor", settingsTestEditorButton, t("settings_editor_running"));
});

settingsReloadButton.addEventListener("click", async () => {
  settingsReloadButton.disabled = true;
  try {
    await loadSettings(t("settings_reloaded"));
  } catch (error) {
    setSettingsFlash(error.message, true);
  } finally {
    settingsReloadButton.disabled = false;
  }
});

languageSelect.addEventListener("change", () => {
  setLanguage(languageSelect.value);
});

tabWorkbench.addEventListener("click", () => activateTab("workbench"));
tabSettings.addEventListener("click", () => activateTab("settings"));

(function init() {
  const savedLanguage = window.localStorage.getItem("pp_lang") || "zh";
  setLanguage(savedLanguage);
  activateTab("workbench");
  loadSettings().catch((error) => {
    setSettingsFlash(error.message, true);
  });
})();
