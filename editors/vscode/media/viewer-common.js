// Shared by the viewers: one handle to VS Code, and buttons that ask the extension to run a command.
window.vscodeApi = acquireVsCodeApi();
document.querySelectorAll("[data-command]").forEach((b) =>
  b.addEventListener("click", () => window.vscodeApi.postMessage({ type: "command", command: b.dataset.command })),
);
