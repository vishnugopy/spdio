(function () {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const errorBox = document.getElementById("error");
  const overlay = document.getElementById("drop-overlay");
  const jobList = document.getElementById("job-list");
  const emptyEl = document.getElementById("queue-empty");
  const countEl = document.getElementById("count");

  const timers = {};
  const rows = {};
  let dragDepth = 0;

  const ACTIVE = ["queued", "loading", "working"];
  let engineReady = false;

  function icon(name) {
    return '<i data-lucide="' + name + '" class="ic"></i>';
  }

  function refreshIcons() {
    if (typeof lucide !== "undefined") lucide.createIcons();
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function show(el) { el.hidden = false; }
  function hide(el) { el.hidden = true; }

  function refreshMeta() {
    const n = jobList.children.length;
    countEl.textContent = n ? n + " song" + (n === 1 ? "" : "s") : "";
    emptyEl.hidden = n > 0;
  }

  function statusInfo(job) {
    switch (job.status) {
      case "queued":
        return { icon: "clock", cls: "state-wait", text: "Waiting in queue…" };
      case "loading":
        return { icon: "loader-circle", cls: "state-active", text: job.message || "Preparing…", spin: true };
      case "working":
        return { icon: "loader-circle", cls: "state-active", text: (job.message || "Working…") + (job.progress ? "  " + job.progress + "%" : ""), spin: true };
      case "done":
        return { icon: "circle-check-big", cls: "state-done", text: "Ready" };
      case "error":
        return { icon: "circle-x", cls: "state-error", text: "Failed" };
      case "cancelled":
        return { icon: "circle-x", cls: "state-cancel", text: "Cancelled" };
      default:
        return { icon: "clock", cls: "", text: "" };
    }
  }

  function buildRow(job) {
    const li = document.createElement("li");
    li.className = "job";
    li.dataset.id = job.id;
    li.innerHTML =
      '<div class="job-state"></div>' +
      '<div class="job-main">' +
        '<div class="job-name"></div>' +
        '<div class="job-sub"></div>' +
        '<div class="job-progress" hidden>' +
          '<div class="progress-track"><div class="progress-bar"></div></div>' +
        '</div>' +
        '<div class="job-audio"></div>' +
        '<div class="job-actions"></div>' +
      '</div>';
    jobList.prepend(li);
    return li;
  }

  function renderActions(row, job) {
    const box = row.querySelector(".job-actions");
    const audioBox = row.querySelector(".job-audio");
    const id = job.id;

    if (job.status === "done") {
      audioBox.innerHTML = "";
      box.innerHTML =
        '<a class="btn btn-outline btn-sm" href="/player/' + id + '">' + icon("play") + " Open</a>" +
        '<button class="btn btn-outline btn-sm danger" data-action="delete">' + icon("trash-2") + " Delete</button>";
    } else if (job.status === "error") {
      audioBox.innerHTML = "";
      box.innerHTML =
        '<button class="btn btn-outline btn-sm" data-action="retry">' + icon("refresh-cw") + " Retry</button>" +
        '<button class="btn btn-outline btn-sm danger" data-action="delete">' + icon("trash-2") + " Delete</button>";
    } else if (job.status === "cancelled") {
      audioBox.innerHTML = "";
      box.innerHTML =
        '<button class="btn btn-outline btn-sm" data-action="retry">' + icon("refresh-cw") + " Retry</button>" +
        '<button class="btn btn-outline btn-sm danger" data-action="delete">' + icon("trash-2") + " Delete</button>";
    } else {
      audioBox.innerHTML = "";
      box.innerHTML =
        '<button class="btn btn-outline btn-sm" data-action="cancel">' + icon("square") + " Cancel task</button>";
    }
  }

  function updateRow(row, job) {
    const info = statusInfo(job);
    row.classList.remove("state-wait", "state-active", "state-done", "state-error", "state-cancel");
    row.classList.add(info.cls || "");

    const stateEl = row.querySelector(".job-state");
    stateEl.className = "job-state " + (info.cls || "");
    stateEl.innerHTML = icon(info.icon);
    if (info.spin) stateEl.querySelector(".ic").classList.add("spin");

    row.querySelector(".job-name").textContent = job.original_name || "Song";

    const sub = row.querySelector(".job-sub");
    if (job.status === "error" && job.error) {
      sub.textContent = job.error;
      sub.classList.add("err");
    } else {
      sub.textContent = info.text;
      sub.classList.remove("err");
    }

    const progressWrap = row.querySelector(".job-progress");
    const bar = row.querySelector(".progress-bar");
    if (job.status === "working" && typeof job.progress === "number") {
      hide(progressWrap);
      show(progressWrap);
      bar.style.width = Math.min(job.progress, 100) + "%";
    } else if (job.status === "queued" || job.status === "loading") {
      hide(progressWrap);
    } else {
      hide(progressWrap);
    }

    renderActions(row, job);
    refreshIcons();
  }

  function upsertRow(job) {
    let row = rows[job.id];
    if (!row) {
      row = buildRow(job);
      rows[job.id] = row;
      refreshMeta();
    }
    updateRow(row, job);
    return row;
  }

  function removeRow(id) {
    clearInterval(timers[id]);
    delete timers[id];
    const row = rows[id];
    if (row) {
      row.remove();
      delete rows[id];
    }
    refreshMeta();
  }

  function poll(id) {
    if (timers[id]) return;
    timers[id] = setInterval(() => {
      fetch("/api/status/" + id)
        .then((r) => r.json())
        .then((job) => {
          if (!job || job.error === "Unknown job.") {
            removeRow(id);
            return;
          }
          updateRow(rows[id], job);
          if (!ACTIVE.includes(job.status)) {
            clearInterval(timers[id]);
            delete timers[id];
          }
        })
        .catch(() => {});
    }, 900);
  }

  function handleFile(file) {
    if (!file) return;
    if (!engineReady) {
      showError("The audio engine is still downloading.");
      return;
    }
    const form = new FormData();
    form.append("file", file);
    fetch("/api/upload", { method: "POST", body: form })
      .then((r) => r.json().then((d) => ({ ok: r.ok, d })))
      .then(({ ok, d }) => {
        if (!ok) throw new Error(d.error || "Upload failed.");
        const placeholder = {
          id: d.job_id,
          original_name: file.name,
          status: "queued",
          progress: 0,
          message: "Waiting in queue",
          error: null,
        };
        upsertRow(placeholder);
        poll(d.job_id);
      })
      .catch((e) => showError(e.message));
  }

  function showError(msg) {
    errorBox.textContent = msg;
    show(errorBox);
    setTimeout(() => hide(errorBox), 6000);
  }

  function deleteJob(id) {
    fetch("/api/jobs/" + id, { method: "DELETE" })
      .then(() => removeRow(id))
      .catch(() => {});
  }

  function retryJob(id, row) {
    fetch("/api/jobs/" + id + "/retry", { method: "POST" })
      .then((r) => r.json())
      .then((d) => {
        if (!d.ok && d.error) throw new Error(d.error);
        updateRow(row, { id, status: "queued", progress: 0, message: "Waiting in queue", error: null, original_name: row.querySelector(".job-name").textContent });
        poll(id);
      })
      .catch((e) => showError(e.message));
  }

  function cancelJob(id, row) {
    const btn = row.querySelector('[data-action="cancel"]');
    if (btn) btn.disabled = true;
    row.querySelector(".job-sub").textContent = "Cancelling…";
    fetch("/api/jobs/" + id + "/cancel", { method: "POST" })
      .then((r) => r.json())
      .then((d) => {
        if (!d.ok && d.error) throw new Error(d.error);
      })
      .catch((e) => showError(e.message));
  }

  // ---- list event delegation ----
  jobList.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const li = btn.closest(".job");
    if (!li) return;
    const id = li.dataset.id;
    const action = btn.dataset.action;
    if (action === "delete") deleteJob(id);
    else if (action === "retry") retryJob(id, li);
    else if (action === "cancel") cancelJob(id, li);
  });

  // ---- dropzone click/keyboard ----
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });
  fileInput.addEventListener("change", () => {
    for (const file of fileInput.files) handleFile(file);
    fileInput.value = "";
  });

  // ---- whole page drop target ----
  function hasFiles(e) {
    return e.dataTransfer && e.dataTransfer.types &&
      Array.prototype.indexOf.call(e.dataTransfer.types, "Files") >= 0;
  }

  window.addEventListener("dragenter", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    dragDepth++;
    overlay.classList.add("active");
  });

  window.addEventListener("dragover", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  });

  window.addEventListener("dragleave", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) overlay.classList.remove("active");
  });

  window.addEventListener("drop", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    dragDepth = 0;
    overlay.classList.remove("active");
    dropzone.classList.remove("dragover");
    for (const file of e.dataTransfer.files) handleFile(file);
  });

  // paste from clipboard
  window.addEventListener("paste", (e) => {
    const files = e.clipboardData && e.clipboardData.files;
    if (files && files.length) {
      e.preventDefault();
      for (const file of files) handleFile(file);
    }
  });

  ["dragenter", "dragover"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => {
      if (hasFiles(e)) dropzone.classList.add("dragover");
    })
  );
  ["dragleave", "drop"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => {
      if (hasFiles(e)) dropzone.classList.remove("dragover");
    })
  );

  // ---- first-run engine ----
  const engineOverlay = document.getElementById("engine-overlay");
  const engineMessage = document.getElementById("engine-message");
  const engineBar = document.getElementById("engine-bar");
  const engineDetail = document.getElementById("engine-detail");
  const engineRetry = document.getElementById("engine-retry");

  function applyEngine(st) {
    engineReady = !!st.ready;
    if (engineReady) {
      hide(engineOverlay);
      return;
    }
    show(engineOverlay);
    engineMessage.textContent = st.message || st.error || "Downloading the audio engine…";
    const pct = typeof st.progress === "number" ? st.progress : 0;
    if (engineBar) engineBar.style.width = Math.min(pct, 100) + "%";
    engineDetail.textContent = st.error ? st.error : (pct ? pct + "%" : "");
    if (engineRetry) engineRetry.disabled = !!st.downloading;
    if (st.error && !st.downloading) show(engineRetry);
    else hide(engineRetry);
    refreshIcons();
  }

  function pollEngine() {
    fetch("/api/engine")
      .then((r) => r.json())
      .then((st) => {
        applyEngine(st);
        if (!st.ready) setTimeout(pollEngine, 500);
      })
      .catch(() => setTimeout(pollEngine, 1500));
  }

  if (engineRetry) {
    engineRetry.addEventListener("click", () => {
      engineRetry.disabled = true;
      fetch("/api/engine/retry", { method: "POST" })
        .then((r) => r.json())
        .then(applyEngine)
        .catch(() => {
          engineRetry.disabled = false;
          engineMessage.textContent = "Could not start the retry. Check the app connection and try again.";
          show(engineRetry);
        });
    });
  }

  pollEngine();

  // ---- load saved history ----
  fetch("/api/history")
    .then((r) => r.json())
    .then((d) => {
      (d.jobs || []).forEach((job) => {
        upsertRow(job);
        if (ACTIVE.includes(job.status)) poll(job.id);
      });
      refreshMeta();
    })
    .catch(() => {});

  refreshIcons();
})();
