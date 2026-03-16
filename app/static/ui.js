const state = {
  jobId: null,
  pollTimer: null,
};
const MODEL_PRESETS = ["gpt-5.4", "gemini-3.1"];

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
const uploadForm = document.getElementById("upload-form");
const photoInput = document.getElementById("photo-input");
const uploadButton = document.getElementById("upload-button");
const confirmButton = document.getElementById("confirm-button");
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
    return;
  }

  planEmpty.hidden = true;
  planContent.hidden = false;
  planSummary.textContent = `${plan.summary} Estimated time: ${plan.estimated_minutes} minutes.`;
  renderList(planGoals, plan.goals);
  renderList(planRisks, plan.risks.length ? plan.risks : ["No major risks identified."]);
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
  confirmButton.hidden = !canConfirm;
  confirmButton.disabled = !canConfirm;
}

function showResult(job) {
  if (!job.result_ready) {
    resultEmpty.hidden = false;
    resultContent.hidden = true;
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
  if (settingsApiKey.value.trim()) {
    payload.llm_api_key = settingsApiKey.value.trim();
  }
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
  settingsKeyMask.textContent = settings.llm_api_key_masked || "Not set";
  settingsStatus.textContent = settings.llm_api_key_configured ? "Key configured" : "Stub fallback";
  settingsEffectivePlanPack.textContent = settings.effective_plan_template_pack;
  settingsEffectiveActionPack.textContent = settings.effective_action_template_pack;
  toggleEditorFields();
}

async function loadSettings(message = "Settings loaded.") {
  const settings = await api("/settings");
  renderSettings(settings);
  setSettingsFlash(message);
}

async function runSettingsTest(path, button, label) {
  button.disabled = true;
  setSettingsFlash(`${label} running...`);
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
    setFlash("Final image is ready.");
  } else if (job.state === "FAILED") {
    stopPolling();
    setFlash(job.error_message || "Job failed.", true);
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
    setFlash("Choose a photo first.", true);
    return;
  }

  stopPolling();
  uploadButton.disabled = true;
  confirmButton.hidden = true;
  confirmButton.disabled = true;
  renderPlan(null);
  showResult({ result_ready: false });
  setFlash("Uploading photo and generating plan...");

  try {
    const formData = new FormData();
    formData.append("file", file);
    const job = await api("/jobs", { method: "POST", body: formData });
    state.jobId = job.id;
    renderJob(job);
    showResult(job);
    const plan = await api(`/jobs/${job.id}/plan`);
    renderPlan(plan);
    setFlash("Plan ready. Review it and confirm when ready.");
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
  setFlash("Plan confirmed. Running editor flow...");

  try {
    const job = await api(`/jobs/${state.jobId}/confirm-plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmed: true }),
    });
    renderJob(job);
    showResult(job);
    if (job.result_ready || job.state === "FAILED") {
      setFlash(job.result_ready ? "Final image is ready." : job.error_message || "Job failed.", job.state === "FAILED");
      return;
    }
    startPolling();
  } catch (error) {
    confirmButton.disabled = false;
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
  setSettingsFlash("Saving settings...");

  try {
    const settings = await api("/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectSettingsPayload()),
    });
    renderSettings(settings);
    setSettingsFlash("Settings saved.");
    setSettingsTestResult("Settings saved. Run a test to verify connectivity.");
  } catch (error) {
    setSettingsFlash(error.message, true);
  } finally {
    settingsSaveButton.disabled = false;
  }
});

settingsTestLlmButton.addEventListener("click", async () => {
  await runSettingsTest("/settings/test-llm", settingsTestLlmButton, "LLM test");
});

settingsTestEditorButton.addEventListener("click", async () => {
  await runSettingsTest("/settings/test-editor", settingsTestEditorButton, "Editor test");
});

settingsReloadButton.addEventListener("click", async () => {
  settingsReloadButton.disabled = true;
  try {
    await loadSettings("Settings reloaded.");
  } catch (error) {
    setSettingsFlash(error.message, true);
  } finally {
    settingsReloadButton.disabled = false;
  }
});

loadSettings().catch((error) => {
  setSettingsFlash(error.message, true);
});
