(function () {
  const id = window.__PLAYER__ && window.__PLAYER__.id;
  if (!id) return;

  const playBtn = document.getElementById("player-play");
  const progressEl = document.getElementById("player-progress");
  const currentEl = document.getElementById("player-current");
  const durEl = document.getElementById("player-duration");
  const waveV = document.getElementById("wave-vocals");
  const waveM = document.getElementById("wave-music");
  const loadingEl = document.getElementById("player-loading");

  const VOCALS_COLOR = "#3b82f6";
  const MUSIC_COLOR = "#facc15";
  const PLAYHEAD_COLOR = "#ef4444";

  const waves = [
    { canvas: waveV, base: null },
    { canvas: waveM, base: null },
  ];

  let vocals = null;
  let music = null;
  let playing = false;
  let ctx = null;
  let wavesLoaded = 0;

  function hideLoader() {
    if (loadingEl) loadingEl.hidden = true;
  }

  function icon(name) {
    return '<i data-lucide="' + name + '" class="ic"></i>';
  }

  function refresh() {
    if (typeof lucide !== "undefined") lucide.createIcons();
  }

  function fmt(t) {
    if (!isFinite(t) || t < 0) t = 0;
    const m = Math.floor(t / 60);
    const s = Math.floor(t % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function setFill(el, pct) {
    el.style.setProperty("--fill", Math.max(0, Math.min(100, pct)) + "%");
  }

  function drawWave(canvas, data, color) {
    const base = document.createElement("canvas");
    base.width = canvas.width;
    base.height = canvas.height;
    const g = base.getContext("2d");
    const w = base.width;
    const h = base.height;
    const mid = h / 2;
    const step = Math.max(1, Math.floor(data.length / w));
    g.fillStyle = color;
    for (let x = 0; x < w; x++) {
      let peak = 0;
      for (let i = 0; i < step; i++) {
        const v = Math.abs(data[x * step + i]);
        if (v > peak) peak = v;
      }
      const hh = Math.max(2, peak * h * 0.95);
      g.fillRect(x, mid - hh / 2, 1, hh);
    }
    const idx = waves.findIndex((o) => o.canvas === canvas);
    if (idx >= 0) waves[idx].base = base;
    renderPlayhead(idx, 0);
  }

  function renderPlayhead(idx, frac) {
    const o = waves[idx];
    if (!o.base) return;
    const g = o.canvas.getContext("2d");
    g.clearRect(0, 0, o.canvas.width, o.canvas.height);
    g.drawImage(o.base, 0, 0);
    const x = Math.round(frac * o.canvas.width);
    const h = o.canvas.height;

    if (frac > 0) {
      g.fillStyle = "rgba(0,0,0,0.22)";
      g.fillRect(0, 0, x, h);
    }

    g.lineCap = "round";
    g.lineWidth = 3;
    g.strokeStyle = PLAYHEAD_COLOR;
    g.beginPath();
    g.moveTo(x, 0);
    g.lineTo(x, h);
    g.stroke();

    g.fillStyle = PLAYHEAD_COLOR;
    g.beginPath();
    g.arc(x, 6, 5, 0, Math.PI * 2);
    g.fill();

    g.fillStyle = "rgba(255,255,255,0.9)";
    g.beginPath();
    g.arc(x, 6, 2, 0, Math.PI * 2);
    g.fill();
  }

  function playheadFrac() {
    if (!vocals || !vocals.duration) return 0;
    return vocals.currentTime / vocals.duration;
  }

  function updatePlayhead() {
    const frac = playheadFrac();
    renderPlayhead(0, frac);
    renderPlayhead(1, frac);
  }

  function seekToFrac(frac) {
    if (!vocals || !vocals.duration) return;
    frac = Math.max(0, Math.min(1, frac));
    const t = frac * vocals.duration;
    vocals.currentTime = t;
    if (music.duration) music.currentTime = t;
    setFill(progressEl, frac * 100);
    progressEl.value = Math.round(frac * 1000);
    currentEl.textContent = fmt(t);
    durEl.textContent = fmt(vocals.duration);
    updatePlayhead();
  }

  function seekFromCanvas(canvas, e) {
    const rect = canvas.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    seekToFrac(frac);
  }

  function bindWaveSeek(canvas) {
    const onMove = (e) => {
      if (e.buttons & 1) seekFromCanvas(canvas, e);
    };
    canvas.addEventListener("mousedown", (e) => {
      seekFromCanvas(canvas, e);
      window.addEventListener("mousemove", onMove);
    });
    window.addEventListener("mouseup", () => {
      window.removeEventListener("mousemove", onMove);
    });
    canvas.addEventListener("touchstart", (e) => {
      e.preventDefault();
      seekFromCanvas(canvas, e.changedTouches[0]);
    }, { passive: false });
    canvas.addEventListener("touchmove", (e) => {
      e.preventDefault();
      seekFromCanvas(canvas, e.changedTouches[0]);
    }, { passive: false });
    canvas.style.cursor = "pointer";
  }

  async function loadWave(url, canvas, color) {
    try {
      const res = await fetch(url);
      const buf = await res.arrayBuffer();
      if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
      const decoded = await ctx.decodeAudioData(buf);
      drawWave(canvas, decoded.getChannelData(0), color);
    } catch (e) {
    } finally {
      wavesLoaded++;
      if (wavesLoaded >= 2) hideLoader();
    }
  }

  vocals = new Audio("/api/preview/" + id + "/vocals");
  music = new Audio("/api/preview/" + id + "/music");
  vocals.preload = "auto";
  music.preload = "auto";

  loadWave("/api/preview/" + id + "/vocals", waveV, VOCALS_COLOR);
  loadWave("/api/preview/" + id + "/music", waveM, MUSIC_COLOR);

  bindWaveSeek(waveV);
  bindWaveSeek(waveM);

  function updatePlayIcon() {
    playBtn.innerHTML = icon(playing ? "pause" : "play");
    refresh();
  }

  vocals.addEventListener("loadedmetadata", () => {
    durEl.textContent = fmt(vocals.duration);
  });

  vocals.addEventListener("timeupdate", () => {
    if (!vocals.duration) return;
    progressEl.value = Math.round((vocals.currentTime / vocals.duration) * 1000);
    setFill(progressEl, (vocals.currentTime / vocals.duration) * 100);
    currentEl.textContent = fmt(vocals.currentTime);
    durEl.textContent = fmt(vocals.duration);
    updatePlayhead();
  });

  vocals.addEventListener("ended", () => {
    playing = false;
    vocals.currentTime = 0;
    if (music.duration) music.currentTime = 0;
    progressEl.value = 0;
    setFill(progressEl, 0);
    currentEl.textContent = fmt(0);
    updatePlayhead();
    updatePlayIcon();
  });

  function togglePlay() {
    if (!vocals) return;
    if (playing) {
      vocals.pause();
      music.pause();
      playing = false;
    } else {
      playing = true;
      vocals.play().catch(() => {});
      music.play().catch(() => {});
    }
    updatePlayIcon();
  }

  function seekBy(delta) {
    if (!vocals || !vocals.duration) return;
    const t = Math.max(0, Math.min(vocals.duration, vocals.currentTime + delta));
    vocals.currentTime = t;
    if (music.duration) music.currentTime = t;
    setFill(progressEl, (t / vocals.duration) * 100);
    progressEl.value = Math.round((t / vocals.duration) * 1000);
    currentEl.textContent = fmt(t);
    durEl.textContent = fmt(vocals.duration);
    updatePlayhead();
  }

  function toggleMute(stream) {
    const a = stream === "vocals" ? vocals : music;
    if (!a) return;
    a.muted = !a.muted;
    const b = document.querySelector('.mute-btn[data-mute="' + stream + '"]');
    if (b) {
      const ic = b.querySelector(".ic");
      if (ic) ic.outerHTML = icon(a.muted ? "volume-x" : "volume-2");
      const label = b.querySelector(".mute-label");
      if (label) label.textContent = a.muted ? "Unmute" : "Mute";
      b.classList.toggle("muted", a.muted);
    }
    refresh();
  }

  playBtn.addEventListener("click", togglePlay);

  progressEl.addEventListener("input", () => {
    if (!vocals.duration) return;
    const t = (progressEl.value / 1000) * vocals.duration;
    vocals.currentTime = t;
    if (music.duration) music.currentTime = t;
    setFill(progressEl, (t / vocals.duration) * 100);
    currentEl.textContent = fmt(t);
    durEl.textContent = fmt(vocals.duration);
    updatePlayhead();
  });

  document.querySelectorAll(".mute-btn").forEach((b) => {
    b.addEventListener("click", () => toggleMute(b.dataset.mute));
  });

  document.querySelectorAll(".vol").forEach((r) => {
    setFill(r, r.value);
    r.addEventListener("input", () => {
      const a = r.dataset.vol === "vocals" ? vocals : music;
      a.volume = r.value / 100;
      setFill(r, r.value);
    });
    r.addEventListener("pointerup", () => r.blur());
  });

  progressEl.addEventListener("pointerup", () => progressEl.blur());

  window.addEventListener("keydown", (e) => {
    const tag = e.target && e.target.tagName ? e.target.tagName.toLowerCase() : "";
    const isField = tag === "input" || tag === "textarea" || tag === "select";
    const key = e.key;
    if (key === " ") {
      if (isField || tag === "button" || tag === "a") return;
      e.preventDefault();
      togglePlay();
    } else if (key === "ArrowLeft" || key === "ArrowRight") {
      if (isField) return;
      e.preventDefault();
      seekBy(key === "ArrowLeft" ? -5 : 5);
    } else if (key === "ArrowUp" || key === "ArrowDown") {
      if (isField) return;
      e.preventDefault();
      toggleMute(key === "ArrowUp" ? "vocals" : "music");
    }
  });

  document.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest("a[href*='/api/download/']");
    if (!a || !window.pywebview || !window.pywebview.api) return;
    e.preventDefault();
    const parts = a.getAttribute("href").split("/").filter(Boolean);
    const jobId = parts[2];
    const stream = parts[3];
    const name = a.getAttribute("download") || (stream + ".mp3");
    window.pywebview.api.save_stem(jobId, stream, name);
  });

  refresh();
})();