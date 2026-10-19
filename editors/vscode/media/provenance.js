// The Provenance view: buttons post a message; the extension does the work.
(() => {
  const vscode = acquireVsCodeApi();
  document.querySelectorAll("[data-msg]").forEach((el) => el.addEventListener("click", (e) => {
    e.preventDefault();
    vscode.postMessage({ type: el.dataset.msg });
  }));
  document.querySelectorAll("[data-tile]").forEach((el) => (el.style.backgroundImage = `url("${el.dataset.tile}")`));
})();
