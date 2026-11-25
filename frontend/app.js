import { STRINGS } from "./js/i18n.js";

const USE_MOCK = false;
let mockEnabled = USE_MOCK;
let lang = "en";
let contacts = [];
let result = null;
let selectedFile = null;
let recorder = null;
let recordingStream = null;
let recordingChunks = [];
let recordingStarted = 0;
let recordingInterval = null;
let recordingStopTimeout = null;
let busy = false;
let creditsRemaining;
let alertEligible = false;
let flowSteps = ["incoming", "checking", "result", "alert", "summary", "feedback"];
let currentStep = "incoming";

const $ = (selector) => document.querySelector(selector);
const t = (key) => STRINGS[lang][key] || key;
const statusBox = $("#status-message");

function setStatus(message, kind = "") {
  statusBox.replaceChildren();
  statusBox.className = `status-message ${kind}`.trim();
  statusBox.hidden = !message;
  if (message) statusBox.textContent = message;
}

function showError(message, retry) {
  statusBox.replaceChildren();
  statusBox.className = "status-message error";
  statusBox.hidden = false;
  const text = document.createElement("p");
  text.textContent = message;
  statusBox.append(text);
  if (retry) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button button-secondary";
    button.textContent = t("retry");
    button.addEventListener("click", retry);
    statusBox.append(button);
  }
}

function apiErrorMessage(code, message) {
  return STRINGS[lang].codes[code] || message || t("errorGeneric");
}

async function readJson(response) {
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error(t("responseError"));
  }
  if (!response.ok) {
    const error = payload && payload.error;
    const failure = new Error(apiErrorMessage(error && error.code, error && error.message));
    failure.retryable = Boolean(error && error.retryable);
    throw failure;
  }
  return payload;
}

async function fetchJson(url, options) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    const error = new Error(t("networkError"));
    error.retryable = true;
    throw error;
  }
  return readJson(response);
}

async function mockJson(filename) {
  let response;
  try {
    response = await fetch(`mock/${filename}`);
  } catch {
    const error = new Error(t("networkError"));
    error.retryable = true;
    throw error;
  }
  if (!response.ok) throw new Error(t("responseError"));
  try {
    return await response.json();
  } catch {
    throw new Error(t("responseError"));
  }
}

function setLanguage(nextLang) {
  lang = nextLang;
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAria));
  });
  document.title = t("pageTitle");
  $("#language").value = lang;
  updateCallerCard();
  if (!$("#dev-mode-indicator").hidden) $("#dev-mode-indicator").textContent = t("mockBadge");
  $("#credits-value").textContent = creditsRemaining === undefined ? t("loading") :
    creditsRemaining === null ? t("unavailable") : String(creditsRemaining);
  if (result) renderResult();
  if (alertEligible) renderAlert();
  renderSteps();
  if (currentStep === "alert" && alertEligible) loadAlerts();
}

function selectedContact() {
  return contacts.find((contact) => contact.id === $("#contact-select").value) || null;
}

function updateCallerCard() {
  const name = selectedContact()?.name || t("claimedCaller");
  $("#claimed-name").textContent = name;
  $("#incoming-label").textContent = t("incomingCall").replace("{name}", name);
  $("#contact-avatar").textContent = name.slice(0, 1).toUpperCase();
}

function populateContacts() {
  const select = $("#contact-select");
  const previous = select.value;
  select.replaceChildren();
  contacts.forEach((contact) => {
    const option = document.createElement("option");
    option.value = contact.id;
    option.textContent = `${contact.name} — ${contact.relationship} (${contact.phone_masked})`;
    select.append(option);
  });
  if (contacts.some((contact) => contact.id === previous)) select.value = previous;
  updateCallerCard();
}

async function loadContacts() {
  contacts = mockEnabled ? await mockJson("contacts.json") : await fetchJson("/api/contacts");
  populateContacts();
}

async function loadCredits(creditsFromCheck) {
  if (creditsFromCheck !== undefined) {
    creditsRemaining = creditsFromCheck;
    $("#credits-value").textContent = creditsRemaining === null ? t("unavailable") : String(creditsRemaining);
    return;
  }
  try {
    const data = mockEnabled ? await mockJson("credits.json") : await fetchJson("/api/credits");
    creditsRemaining = data.available === null ? null : data.available;
    $("#credits-value").textContent = creditsRemaining === null ? t("unavailable") : String(creditsRemaining);
  } catch (error) {
    creditsRemaining = null;
    $("#credits-value").textContent = t("unavailable");
    showError(error.message, error.retryable ? () => loadCredits() : null);
  }
}

function renderSteps() {
  const list = $("#step-list");
  list.replaceChildren();
  const labels = {
    incoming: "stepIncoming", checking: "stepChecking", result: "stepResult", alert: "stepAlert",
    summary: "stepSummary", feedback: "stepFeedback"
  };
  const visibleSteps = flowSteps.filter((step) => step !== "alert" || alertEligible);
  visibleSteps.forEach((step, index) => {
    const item = document.createElement("li");
    if (step === currentStep) item.setAttribute("aria-current", "step");
    if (visibleSteps.indexOf(currentStep) > index) item.classList.add("done");
    const number = document.createElement("span");
    number.className = "step-number";
    number.textContent = String(index + 1);
    const label = document.createElement("span");
    label.textContent = t(labels[step]);
    item.append(number, label);
    list.append(item);
  });
}

function navigate(step) {
  if (step === "alert" && !alertEligible) step = "summary";
  currentStep = step;
  document.querySelectorAll(".step-panel").forEach((panel) => { panel.hidden = panel.id !== `step-${step}`; });
  renderSteps();
  setStatus("");
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (step === "alert") loadAlerts();
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function makeMetric(label, value) {
  const item = element("div", "metric");
  item.append(element("strong", "", value), element("span", "", label));
  return item;
}

function renderResult() {
  const host = $("#result-content");
  host.replaceChildren();
  if (!result) return;
  const risk = ["high", "medium", "low"].includes(result.risk) ? result.risk : "medium";
  const riskTitle = t(`risk${risk[0].toUpperCase()}${risk.slice(1)}`);
  const card = element("div", `risk-card ${risk}`);
  const icon = element("span", "risk-icon", t(`${risk}IconText`));
  icon.setAttribute("aria-hidden", "true");
  const cardText = element("div");
  cardText.append(element("h3", "", riskTitle));
  cardText.append(element("p", "", result.verdict === "real" ? t("realVerdict") : t("fakeVerdict")));
  card.append(icon, cardText);
  host.append(card);

  const metrics = element("div", "metrics");
  metrics.append(
    makeMetric(t("verdict"), result.verdict === "real" ? t("realVerdict") : t("fakeVerdict")),
    makeMetric(t("aiSignal"), `${Math.round(Number(result.score) * 100)}%`),
    makeMetric(t("clipLength"), `${Number(result.duration_seconds).toFixed(1)} ${t("secondsUnit")}`)
  );
  host.append(metrics);
  const timelineTitle = element("h3", "subheading", t("timelineHeading"));
  const timelineDescription = element("p", "field-hint", t("timelineDescription"));
  host.append(timelineTitle, timelineDescription);
  const segments = Array.isArray(result.segments) ? result.segments : [];
  const duration = Math.max(0.1, Number(result.duration_seconds) || 0.1);
  const timeline = element("div", "timeline");
  timeline.setAttribute("role", "group");
  timeline.setAttribute("aria-label", t("timelineHeading"));
  timeline.style.height = `${Math.max(104, segments.length * 24 + 20)}px`;
  segments.forEach((segment, index) => {
    const score = Math.max(0, Math.min(1, Number(segment.score) || 0));
    const bar = element("button", `timeline-segment ${risk}`);
    bar.type = "button";
    const start = Math.max(0, Math.min(duration, Number(segment.start) || 0));
    const end = Math.max(start, Math.min(duration, Number(segment.end) || start));
    const detail = `${start.toFixed(1)}–${end.toFixed(1)} ${t("secondsUnit")}, ${Math.round(score * 100)}%`;
    bar.title = detail;
    bar.setAttribute("aria-label", detail);
    bar.style.left = `${(start / duration) * 100}%`;
    bar.style.width = `${Math.max(1, ((end - start) / duration) * 100)}%`;
    bar.style.top = `${10 + index * 24}px`;
    bar.style.height = `${Math.round(6 + score * 16)}px`;
    timeline.append(bar);
  });
  if (!timeline.childElementCount) timeline.append(element("p", "", t("unavailable")));
  host.append(timeline);
  const scale = element("div", "timeline-scale");
  scale.append(element("span", "", `0 ${t("secondsUnit")}`), element("span", "", `${Number(result.duration_seconds).toFixed(1)} ${t("secondsUnit")}`));
  host.append(scale);

  host.append(element("h3", "subheading", t("adviceHeading")));
  const adviceList = element("ul", "advice-list");
  (Array.isArray(result.advice) ? result.advice : []).forEach((advice) => adviceList.append(element("li", "", advice)));
  host.append(adviceList);
  if (result.limitations && result.limitations.length) {
    const details = document.createElement("details");
    details.append(element("summary", "", t("limitations")));
    const list = document.createElement("ul");
    result.limitations.forEach((limitation) => list.append(element("li", "", limitation)));
    details.append(list);
    host.append(details);
  }
  host.append(element("p", "disclaimer", result.disclaimer || t("footerDisclaimer")));
  renderAction(host);
}

function renderAction(host) {
  const action = result.action || { type: "proceed_with_caution" };
  const panel = element("section", `action-panel ${action.type === "block_and_callback" ? "block" : ""}`);
  if (action.type === "block_and_callback") {
    panel.append(element("h3", "", t("actionBlockTitle")));
    const contact = selectedContact();
    panel.append(element("p", "", `${t("callbackLabel")} ${action.callback_number_masked || contact?.callback_number_masked || t("unavailable")}`));
    panel.append(element("p", "", `${t("safeWordLabel")} ${action.safe_word_hint || contact?.safe_word_hint || t("unavailable")}`));
    const buttons = element("div", "action-buttons");
    const verified = element("button", "button button-secondary", t("verified"));
    const unsure = element("button", "button button-secondary", t("unsure"));
    verified.type = unsure.type = "button";
    verified.addEventListener("click", () => setStatus(t("callVerified")));
    unsure.addEventListener("click", () => setStatus(t("callUnsure")));
    buttons.append(verified, unsure);
    panel.append(buttons);
  } else if (action.type === "verify_first") {
    panel.append(element("h3", "", t("actionVerifyTitle")), element("p", "", t("verifySteps")));
  } else {
    panel.append(element("h3", "", t("actionCautionTitle")), element("p", "", t("cautionText")));
  }
  if (action.note) panel.append(element("p", "", `${t("actionNote")}: ${action.note}`));
  host.append(panel);
}

function renderAlert() {
  const host = $("#alert-content");
  host.replaceChildren();
  const contact = selectedContact();
  if (!contact) {
    host.append(element("p", "", t("contactsError")));
    return;
  }
  const riskText = t(`risk${result.risk[0].toUpperCase()}${result.risk.slice(1)}`);
  const card = element("div", "alert-card");
  card.append(element("h3", "", t("alertCardTitle").replace("{name}", contact.name)));
  const preview = element("p", "message-preview", t("alertPreview").replace("{name}", contact.name).replace("{risk}", riskText));
  card.append(preview);
  const label = element("label", "confirm-label");
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.id = "confirm-alert";
  const labelText = element("span", "", t("confirmAlert"));
  label.append(checkbox, labelText);
  card.append(label);
  const send = element("button", "button button-primary", t("sendAlert"));
  send.type = "button";
  send.disabled = true;
  checkbox.addEventListener("change", () => { send.disabled = !checkbox.checked || busy; });
  send.addEventListener("click", () => sendAlert(send, checkbox));
  card.append(send);
  host.append(card);
  const heading = element("h3", "subheading", t("alertsLog"));
  const log = element("ul", "alert-log");
  log.id = "alerts-log";
  host.append(heading, log);
}

async function loadAlerts() {
  const host = $("#alerts-log");
  if (!host) return;
  host.replaceChildren();
  try {
    const alerts = mockEnabled ? await mockJson("alerts.json") : await fetchJson("/api/alerts");
    if (!Array.isArray(alerts) || alerts.length === 0) host.append(element("li", "", t("noAlerts")));
    (Array.isArray(alerts) ? alerts : []).forEach((alert) => {
      const line = `${alert.timestamp || ""} · ${alert.message || ""} · ${alert.status || ""}`;
      host.append(element("li", "", line));
    });
  } catch (error) {
    const item = element("li");
    item.append(element("span", "", error.message));
    if (error.retryable) {
      const retry = element("button", "text-button", t("retry"));
      retry.type = "button";
      retry.addEventListener("click", loadAlerts);
      item.append(retry);
    }
    host.append(item);
  }
}

async function sendAlert(button, checkbox) {
  if (!checkbox.checked || busy) return;
  busy = true;
  button.disabled = true;
  try {
    const payload = { operation_id: result.operation_id, contact_id: selectedContact().id, confirm: true };
    const response = mockEnabled
      ? { ok: true, status: "logged" }
      : await fetchJson("/api/alert", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const key = response.status === "sent" ? "alertSent" : response.status === "failed" ? "alertFailed" : "alertLogged";
    setStatus(t(key), response.status === "failed" ? "error" : "");
    await loadAlerts();
  } catch (error) {
    showError(error.message, error.retryable ? () => sendAlert(button, checkbox) : null);
    button.disabled = false;
  } finally {
    busy = false;
  }
}

function updateClaimEligibility() {
  alertEligible = Boolean(result && result.claimed_contact && ["medium", "high"].includes(result.risk));
  if (!alertEligible) flowSteps = ["incoming", "checking", "result", "summary", "feedback"];
  else flowSteps = ["incoming", "checking", "result", "alert", "summary", "feedback"];
  document.querySelector('#step-summary [data-back]').dataset.back = alertEligible ? "alert" : "result";
  if (alertEligible) renderAlert();
  renderSteps();
}

function displayDuration(file) {
  return new Promise((resolve, reject) => {
    const audio = document.createElement("audio");
    const objectUrl = URL.createObjectURL(file);
    const cleanup = () => {
      URL.revokeObjectURL(objectUrl);
      audio.removeAttribute("src");
    };
    audio.preload = "metadata";
    audio.onloadedmetadata = () => {
      const duration = audio.duration;
      cleanup();
      if (Number.isFinite(duration)) resolve(duration);
      else resolve(null);
    };
    audio.onerror = () => {
      cleanup();
      reject(new Error(t("fileUnreadable")));
    };
    audio.src = objectUrl;
  });
}

async function validateFile(file, isRecording = false) {
  if (!file) throw new Error(t("noAudio"));
  if (!file.type || !file.type.toLowerCase().startsWith("audio/")) throw new Error(t("badType"));
  if (file.size >= 100 * 1024 * 1024) throw new Error(t("tooLarge"));
  const duration = await displayDuration(file);
  if (duration !== null && duration < 4 && isRecording) throw new Error(t("recordingTooShort"));
  if (duration !== null && (duration < 4 || duration > 120)) throw new Error(t("durationInvalid"));
}

function startRecording() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === "undefined") {
    showError(t("recorderUnsupported"));
    return;
  }
  navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
    recordingStream = stream;
    recordingChunks = [];
    try {
      recorder = new MediaRecorder(stream);
    } catch {
      stream.getTracks().forEach((track) => track.stop());
      recordingStream = null;
      cancelRecording.hidden = true;
      showError(t("recorderUnsupported"));
      return;
    }
    recorder.ondataavailable = (event) => {
      if (event.data.size) recordingChunks.push(event.data);
    };
    recorder.onstop = () => {
      const wasCancelled = recorder && recorder.cancelRecording;
      if (recordingStream) recordingStream.getTracks().forEach((track) => track.stop());
      recordingStream = null;
      $("#record-start").disabled = false;
      $("#record-stop").disabled = true;
      cancelRecording.hidden = true;
      if (recordingInterval) window.clearInterval(recordingInterval);
      recordingInterval = null;
      if (recordingStopTimeout) window.clearTimeout(recordingStopTimeout);
      recordingStopTimeout = null;
      if (wasCancelled) {
        recordingChunks = [];
        showError(t("recordingCancelled"));
        return;
      }
      const blob = new Blob(recordingChunks, { type: recorder.mimeType || "audio/webm" });
      if (blob.size === 0) {
        showError(t("recordingCancelled"));
        return;
      }
      if (blob.size >= 100 * 1024 * 1024) {
        showError(t("tooLarge"));
        return;
      }
      const extension = blob.type.includes("ogg") ? "ogg" : blob.type.includes("mp4") ? "m4a" : "webm";
      selectedFile = new File([blob], `recording.${extension}`, { type: blob.type });
      $("#audio-file").value = "";
      $("#record-timer").textContent = formatTime(Math.floor((Date.now() - recordingStarted) / 1000));
      validateFile(selectedFile, true).then(() => setStatus("")).catch((error) => {
        selectedFile = null;
        showError(error.message);
      });
    };
    try {
      recorder.start();
    } catch {
      stream.getTracks().forEach((track) => track.stop());
      recordingStream = null;
      recorder = null;
      cancelRecording.hidden = true;
      showError(t("recorderUnsupported"));
      return;
    }
    recordingStarted = Date.now();
    $("#record-start").disabled = true;
    $("#record-stop").disabled = false;
    $("#record-timer").textContent = "00:00";
    recordingInterval = window.setInterval(() => {
      const seconds = Math.floor((Date.now() - recordingStarted) / 1000);
      $("#record-timer").textContent = formatTime(seconds);
    }, 250);
    recordingStopTimeout = window.setTimeout(() => {
      if (recorder && recorder.state === "recording") recorder.stop();
    }, 120000);
  }).catch((error) => {
    cancelRecording.hidden = true;
    if (error && error.name === "NotAllowedError") showError(t("microphoneDenied"));
    else showError(t("recorderUnsupported"));
  });
}

function formatTime(seconds) {
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function stopRecording(cancel = false) {
  if (!recorder || recorder.state !== "recording") return;
  recorder.cancelRecording = cancel;
  recorder.stop();
}

async function runCheck() {
  if (busy) return;
  const isMock = mockEnabled;
  const file = selectedFile || $("#audio-file").files[0];
  if (!isMock) {
    try {
      await validateFile(file);
    } catch (error) {
      showError(error.message);
      return;
    }
  }
  busy = true;
  $("#check-button").disabled = true;
  navigate("checking");
  setStatus("");
  try {
    if (isMock) {
      result = await mockJson(`check_${$("#sample-select").value}.json`);
      const contact = selectedContact();
      if (contact && result.claimed_contact) {
        result.claimed_contact = { id: contact.id };
        if (result.action) {
          result.action.callback_number_masked = contact.callback_number_masked;
          result.action.safe_word_hint = contact.safe_word_hint;
        }
      }
    } else {
      const form = new FormData();
      form.append("file", file);
      form.append("lang", lang);
      if ($("#contact-select").value) form.append("claimed_contact_id", $("#contact-select").value);
      result = await fetchJson("/api/check", { method: "POST", body: form });
    }
    updateClaimEligibility();
    renderResult();
    navigate("result");
    await loadCredits(result.credits_left);
  } catch (error) {
    if (error.retryable) navigate("incoming");
    showError(error.message, error.retryable ? runCheck : null);
  } finally {
    busy = false;
    $("#check-button").disabled = false;
  }
}

function summaryText() {
  const contact = selectedContact();
  const note = $("#incident-note").value.trim();
  const caller = $("#caller-name").value.trim();
  const lines = [
    t("summaryHeading"),
    `${t("callerName")}: ${caller || t("unavailable")}`,
    `${t("contactClaimed")}: ${contact ? contact.name : t("unavailable")}`,
    `${t("riskLabel")}: ${result ? result.risk : t("unavailable")}`,
    `${t("verdictLabel")}: ${result ? (result.verdict === "real" ? t("realVerdict") : t("fakeVerdict")) : t("unavailable")}`,
    `${t("signalLabel")}: ${result ? Math.round(Number(result.score) * 100) : "—"}%`,
    `${t("durationLabel")}: ${result ? Number(result.duration_seconds).toFixed(1) : "—"} ${t("secondsUnit")}`,
    `${t("operationLabel")}: ${result ? result.operation_id : t("unavailable")}`,
    `${t("happenedLabel")}: ${note || t("unavailable")}`,
    result ? result.disclaimer : t("footerDisclaimer"),
    t("notFir")
  ];
  return lines.join("\n");
}

function openPrintableSummary() {
  if (!result) return;
  if (mockEnabled) {
    const printWindow = window.open("about:blank", "_blank");
    if (!printWindow) {
      showError(t("errorGeneric"));
      return;
    }
    printWindow.opener = null;
    printWindow.document.title = t("summaryHeading");
    const heading = printWindow.document.createElement("h1");
    heading.textContent = t("summaryHeading");
    const content = printWindow.document.createElement("pre");
    content.textContent = summaryText();
    printWindow.document.body.replaceChildren(heading, content);
    return;
  }
  const params = new URLSearchParams({ format: "html", lang });
  const caller = $("#caller-name").value.trim();
  if (caller) params.set("caller", caller);
  const report = window.open(`/api/evidence/${encodeURIComponent(result.operation_id)}?${params.toString()}`, "_blank");
  if (!report) {
    showError(t("errorGeneric"));
    return;
  }
  report.opener = null;
  const note = $("#incident-note").value.trim();
  if (note) {
    const appendNote = () => {
      const noteLabel = report.document.createElement("h2");
      noteLabel.textContent = t("happenedLabel");
      const noteText = report.document.createElement("p");
      noteText.textContent = note;
      report.document.body.append(noteLabel, noteText);
    };
    if (report.document.readyState === "complete") appendNote();
    else report.addEventListener("load", appendNote, { once: true });
  }
}

async function copySummary() {
  try {
    await navigator.clipboard.writeText(summaryText());
    setStatus(t("copied"));
  } catch {
    showError(t("copyFailed"));
  }
}

async function sendFeedback() {
  if (busy) return;
  const selected = document.querySelector('input[name="feedback-correct"]:checked');
  if (!selected) {
    setStatus(t("feedbackMissing"), "error");
    return;
  }
  const payload = {
    correct: selected.value === "true",
    label: $("#feedback-label").value || null,
    note: null
  };
  busy = true;
  $("#send-feedback").disabled = true;
  try {
    if (!mockEnabled) {
      await fetchJson(`/api/feedback/${encodeURIComponent(result.operation_id)}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
      });
    }
    setStatus(t("feedbackSent"));
  } catch (error) {
    showError(error.message, error.retryable ? sendFeedback : null);
  } finally {
    busy = false;
    $("#send-feedback").disabled = false;
  }
}

async function toggleMockMode() {
  if (busy) return;
  mockEnabled = !mockEnabled;
  $("#dev-mode-indicator").hidden = !mockEnabled;
  $("#dev-mode-indicator").textContent = t("mockBadge");
  $("#sample-controls").hidden = !mockEnabled;
  setStatus("");
  result = null;
  alertEligible = false;
  flowSteps = ["incoming", "checking", "result", "alert", "summary", "feedback"];
  selectedFile = null;
  $("#audio-file").value = "";
  try {
    await loadContacts();
    await loadCredits();
    navigate("incoming");
  } catch (error) {
    showError(error.message, error.retryable ? toggleMockMode : null);
  }
}

$("#language").addEventListener("change", (event) => setLanguage(event.target.value));
$("#contact-select").addEventListener("change", updateCallerCard);
$("#audio-file").addEventListener("change", async (event) => {
  selectedFile = event.target.files[0] || null;
  if (!selectedFile) return;
  try {
    await validateFile(selectedFile);
    setStatus("");
  } catch (error) {
    selectedFile = null;
    event.target.value = "";
    showError(error.message);
  }
});
$("#record-start").addEventListener("click", startRecording);
$("#record-stop").addEventListener("click", () => stopRecording(false));
$("#check-button").addEventListener("click", runCheck);
$("#result-next").addEventListener("click", () => navigate(alertEligible ? "alert" : "summary"));
$("#alert-next").addEventListener("click", () => navigate("summary"));
$("#print-summary").addEventListener("click", openPrintableSummary);
$("#copy-summary").addEventListener("click", copySummary);
$("#send-feedback").addEventListener("click", sendFeedback);
$("#refresh-credits").addEventListener("click", () => loadCredits());
document.querySelectorAll("[data-back]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.back)));
document.querySelectorAll("[data-forward]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.forward)));
document.addEventListener("keydown", (event) => {
  if (event.shiftKey && event.key.toLowerCase() === "m") {
    event.preventDefault();
    toggleMockMode();
  }
});

setLanguage(lang);
$("#record-start").hidden = typeof MediaRecorder === "undefined" || !navigator.mediaDevices;
$("#record-stop").hidden = $("#record-start").hidden;
const cancelRecording = element("button", "button button-secondary", t("cancelRecording"));
cancelRecording.type = "button";
cancelRecording.dataset.cancelRecording = "true";
cancelRecording.dataset.i18n = "cancelRecording";
cancelRecording.hidden = true;
cancelRecording.addEventListener("click", () => stopRecording(true));
$("#record-box").querySelector(".record-controls").append(cancelRecording);
const recordingUnavailable = typeof MediaRecorder === "undefined" || !navigator.mediaDevices;
$("#record-start").addEventListener("click", () => { cancelRecording.hidden = false; });
$("#record-stop").addEventListener("click", () => { cancelRecording.hidden = true; });
$("#recording-unavailable").hidden = !recordingUnavailable;
loadContacts().catch((error) => showError(error.message, error.retryable ? loadContacts : null));
loadCredits();
