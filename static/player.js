(function () {
  const id = window.__PLAYER__ && window.__PLAYER__.id;
  if (!id) return;

  const playBtn = document.getElementById("player-play");
  const progressEl = document.getElementById("player-progress");
  const currentEl = document.getElementById("player-current");
  const durEl = document.getElementById("player-duration");
  const waveV = document.getElementById("wave-vocals");
  const waveM = document.getElementById("wave-music");

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
    if (frac > 0) {
      const x = Math.round(frac * o.canvas.width);
      g.fillStyle = PLAYHEAD_COLOR;
      g.fillRect(x - 1, 0, 2, o.canvas.height);
    }
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

  async function loadWave(url, canvas, color) {
    try {
      const res = await fetch(url);
      const buf = await res.arrayBuffer();
      if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
      const decoded = await ctx.decodeAudioData(buf);
      drawWave(canvas, decoded.getChannelData(0), color);
    } catch (e) {}
  }

  vocals = new Audio("/api/preview/" + id + "/vocals");
  music = new Audio("/api/preview/" + id + "/music");
  vocals.preload = "auto";
  music.preload = "auto";

  loadWave("/api/preview/" + id + "/vocals", waveV, VOCALS_COLOR);
  loadWave("/api/preview/" + id + "/music", waveM, MUSIC_COLOR);

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
    currentEl.textContent = fmt(vocals.currentTime);
    durEl.textContent = fmt(vocals.duration);
    updatePlayhead();
  });

  vocals.addEventListener("ended", () => {
    playing = false;
    updatePlayIcon();
  });

  playBtn.addEventListener("click", () => {
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
  });

  progressEl.addEventListener("input", () => {
    if (!vocals.duration) return;
    const t = (progressEl.value / 1000) * vocals.duration;
    vocals.currentTime = t;
    if (music.duration) music.currentTime = t;
    currentEl.textContent = fmt(t);
    durEl.textContent = fmt(vocals.duration);
    updatePlayhead();
  });

  document.querySelectorAll(".mute-btn").forEach((b) => {
    b.addEventListener("click", () => {
      const stream = b.dataset.mute;
      const a = stream === "vocals" ? vocals : music;
      a.muted = !a.muted;
      b.innerHTML = icon(a.muted ? "volume-x" : "volume-2");
      b.classList.toggle("muted", a.muted);
      refresh();
    });
  });

  document.querySelectorAll(".vol").forEach((r) => {
    r.addEventListener("input", () => {
      const a = r.dataset.vol === "vocals" ? vocals : music;
      a.volume = r.value / 100;
    });
  });

  refresh();
})();