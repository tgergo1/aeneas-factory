// The Library view: search as you type, show results as thumbnails, open on click.
(() => {
  const vscode = acquireVsCodeApi();
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const saved = vscode.getState() || {};
  for (const k of ["q", "kind", "origin", "licence"]) if (saved[k] !== undefined) $(k).value = saved[k];
  if (saved.here !== undefined) $("here").checked = saved.here;

  let timer;
  function search() {
    const q = { q: $("q").value.trim(), kind: $("kind").value, origin: $("origin").value, licence: $("licence").value.trim(), here: $("here").checked };
    vscode.setState(q);
    $("status").textContent = "Searching…";
    vscode.postMessage({ type: "search", ...q });
  }
  const soon = () => { clearTimeout(timer); timer = setTimeout(search, 250); };
  $("search").addEventListener("submit", (e) => { e.preventDefault(); search(); });
  ["q", "licence"].forEach((id) => $(id).addEventListener("input", soon));
  ["kind", "origin", "here"].forEach((id) => $(id).addEventListener("change", search));

  window.addEventListener("message", ({ data: m }) => {
    if (m.type === "error") {
      $("status").textContent = m.message;
      $("results").innerHTML = "";
      return;
    }
    if (m.type !== "results") return;
    $("status").textContent = `${m.items.length} result${m.items.length === 1 ? "" : "s"}${m.project ? ` in ${m.project}` : ""}`;
    $("results").innerHTML = m.items.map((it, i) => `
      <div class="card${it.exists ? "" : " missing"}" data-i="${i}" tabindex="0" title="${esc(it.prompt || it.name)}${it.exists ? "" : " (file missing)"}">
        <div class="pic">${it.thumb ? `<img src="${esc(it.thumb)}" alt="" loading="lazy">` : `<span class="kind">${esc(it.kind)}</span>`}</div>
        <div class="name">${esc(it.name)}</div>
        <div class="meta"><span class="chip${/cc0|public/i.test(it.licence) ? " ok" : ""}">${esc(it.licence)}</span> ${esc(it.origin === "generated" ? "made here" : it.source || "")}</div>
        <div class="actions"><a href="#" data-a="provenance">record</a> · <a href="#" data-a="reveal">reveal</a></div>
      </div>`).join("");
    $("results").querySelectorAll(".card").forEach((card) => {
      const it = m.items[Number(card.dataset.i)];
      const open = () => it.exists && vscode.postMessage({ type: "open", path: it.path });
      card.addEventListener("click", (e) => {
        const a = e.target.closest("[data-a]");
        if (a) {
          e.preventDefault();
          e.stopPropagation();
          vscode.postMessage({ type: a.dataset.a, path: it.path });
        } else open();
      });
      card.addEventListener("keydown", (e) => e.key === "Enter" && open());
    });
  });
  search();
})();
