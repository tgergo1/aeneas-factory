// The live preview: shows the latest render of the source being edited.
(() => {
  const vscode = acquireVsCodeApi();
  const main = document.getElementById("preview");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const kb = (n) => (n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

  window.addEventListener("message", ({ data: m }) => {
    if (m.type !== "show") return;
    const status = m.status === "rendering" ? `<span class="chip">rendering…</span>`
      : m.status === "failed" ? `<span class="chip warn">failed</span>`
      : `<span class="chip ok">rendered${m.seconds ? ` in ${m.seconds.toFixed(1)} s` : ""}</span>`;
    let body = "";
    if (m.status === "failed") body += `<pre class="error">${esc(m.error)}</pre>`;
    if (m.image) body += `<div class="canvas checker"><img src="${esc(m.image)}" alt="${esc(m.outName)}"></div>`;
    if (m.audio) body += `${m.wave ? `<img class="wave" src="${esc(m.wave)}" alt="waveform">` : ""}<audio controls src="${esc(m.audio)}"></audio>`;
    if (m.kind === "dialogue" && m.size && m.status !== "failed") body += `<p>Compiled for the game engine: <code>${esc(m.outName)}</code>, ${kb(m.size)}.</p>`;
    const links = m.size ? `<a href="#" data-msg="open">Open ${esc(m.outName)}</a> · <a href="#" data-msg="provenance">Provenance</a>` : "";
    main.innerHTML = `<div class="toolbar"><strong>${esc(m.source)}</strong> → ${esc(m.outName)} ${status}<span class="spacer"></span>${links}</div>${body}`;
    main.dataset.status = m.status;
    main.querySelectorAll("[data-msg]").forEach((a) => a.addEventListener("click", (e) => {
      e.preventDefault();
      vscode.postMessage({ type: a.dataset.msg, path: m.out });
    }));
  });
  vscode.postMessage({ type: "ready" });
})();
