// The .wav viewer: decodes the file in the page, draws its waveform, plays it, and measures it.
(() => {
  const canvas = document.getElementById("wave");
  const head = document.getElementById("playhead");
  const stats = document.getElementById("stats");
  const playBtn = document.getElementById("play");
  const loop = document.getElementById("loop");
  const ctx = new AudioContext();
  let buffer, source, startedAt = 0, offset = 0, playing = false, fileRate;

  // Web Audio resamples to the device's rate; the file's own rate is in its "fmt " chunk.
  function wavRate(bytes) {
    const v = new DataView(bytes);
    if (v.byteLength < 12 || v.getUint32(0) !== 0x52494646 || v.getUint32(8) !== 0x57415645) return undefined;
    for (let at = 12; at + 8 <= v.byteLength; ) {
      const id = v.getUint32(at), size = v.getUint32(at + 4, true);
      if (id === 0x666d7420 && at + 16 <= v.byteLength) return v.getUint32(at + 12, true);
      at += 8 + size + (size % 2);
    }
    return undefined;
  }

  const db = (v) => (v > 0 ? (20 * Math.log10(v)).toFixed(1) : "-inf");

  function draw() {
    if (!buffer) return;
    const w = (canvas.width = canvas.clientWidth * devicePixelRatio);
    const h = (canvas.height = canvas.clientHeight * devicePixelRatio);
    const g = canvas.getContext("2d");
    const css = getComputedStyle(document.body);
    g.fillStyle = css.getPropertyValue("--vscode-textLink-foreground") || "#3794ff";
    const data = buffer.getChannelData(0);
    const extra = buffer.numberOfChannels > 1 ? buffer.getChannelData(1) : null;
    const step = data.length / w;
    for (let x = 0; x < w; x++) {
      let lo = 1, hi = -1;
      const end = Math.min(data.length, Math.floor((x + 1) * step));
      for (let i = Math.floor(x * step); i < end; i++) {
        const v = extra ? (data[i] + extra[i]) / 2 : data[i];
        if (v < lo) lo = v;
        if (v > hi) hi = v;
      }
      if (hi < lo) continue;
      g.fillRect(x, ((1 - hi) / 2) * h, 1, Math.max(1, ((hi - lo) / 2) * h));
    }
  }

  function measure() {
    let peak = 0, sum = 0, n = 0;
    for (let c = 0; c < buffer.numberOfChannels; c++) {
      const d = buffer.getChannelData(c);
      for (let i = 0; i < d.length; i++) {
        const a = Math.abs(d[i]);
        if (a > peak) peak = a;
        sum += d[i] * d[i];
      }
      n += d.length;
    }
    const rms = Math.sqrt(sum / Math.max(1, n));
    stats.textContent = `${buffer.duration.toFixed(2)} s · ${fileRate || buffer.sampleRate} Hz · ${buffer.numberOfChannels === 1 ? "mono" : buffer.numberOfChannels + " channels"} · peak ${db(peak)} dBFS · RMS ${db(rms)} dBFS`;
    window.__aeneasAudio = { seconds: buffer.duration, peak, rms };
  }

  function position() {
    return playing ? (ctx.currentTime - startedAt) % buffer.duration : offset;
  }

  function stop(keep) {
    if (source) {
      source.onended = null;
      source.stop();
      source = undefined;
    }
    if (keep) offset = position();
    playing = false;
    playBtn.textContent = "Play";
  }

  function play(from) {
    stop(false);
    ctx.resume();
    source = ctx.createBufferSource();
    source.buffer = buffer;
    source.loop = loop.checked;
    source.connect(ctx.destination);
    source.onended = () => { playing = false; offset = 0; playBtn.textContent = "Play"; };
    source.start(0, from);
    startedAt = ctx.currentTime - from;
    playing = true;
    playBtn.textContent = "Pause";
  }

  function tick() {
    if (buffer) head.style.left = `${(position() / buffer.duration) * 100}%`;
    requestAnimationFrame(tick);
  }

  fetch(canvas.dataset.src)
    .then((r) => r.arrayBuffer())
    .then((b) => {
      fileRate = wavRate(b);
      return ctx.decodeAudioData(b);
    })
    .then((b) => {
      buffer = b;
      draw();
      measure();
      tick();
    })
    .catch((e) => (stats.textContent = `Could not decode the audio: ${e.message || e}`));

  playBtn.addEventListener("click", () => (playing ? stop(true) : play(offset)));
  loop.addEventListener("change", () => source && (source.loop = loop.checked));
  canvas.addEventListener("click", (e) => {
    if (!buffer) return;
    const at = (e.offsetX / canvas.clientWidth) * buffer.duration;
    if (playing) play(at);
    else offset = at;
  });
  document.addEventListener("keydown", (e) => {
    if (e.code === "Space" && buffer) {
      e.preventDefault();
      playing ? stop(true) : play(offset);
    }
  });
  new ResizeObserver(draw).observe(canvas);
})();
