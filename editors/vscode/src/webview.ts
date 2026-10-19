// A strict page shell for every webview: scripts only with a nonce, files only from allowed folders.
// Webviews never talk to the service; they post messages and the extension does the work.
import { randomBytes } from "crypto";
import * as vscode from "vscode";

export function nonce(): string {
  return randomBytes(16).toString("base64");
}

export function esc(s: unknown): string {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

export function page(webview: vscode.Webview, extensionUri: vscode.Uri, opts: { title: string; body: string; scripts?: string[]; state?: unknown; wasm?: boolean }): string {
  const n = nonce();
  const css = webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, "media", "style.css"));
  const scripts = (opts.scripts ?? []).map((s) => {
    const dir = s.endsWith("glb-viewer.js") ? "dist" : "media";
    return `<script nonce="${n}" src="${webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, dir, s))}"></script>`;
  });
  const state = opts.state === undefined ? "" :
    `<script nonce="${n}" id="state" type="application/json">${JSON.stringify(opts.state).replace(/</g, "\\u003c")}</script>`;
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${webview.cspSource} blob: data:; media-src ${webview.cspSource} blob:; style-src ${webview.cspSource}; script-src 'nonce-${n}'${opts.wasm ? " 'wasm-unsafe-eval'" : ""}; connect-src ${webview.cspSource} blob: data:;">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="${css}">
<title>${esc(opts.title)}</title>
</head>
<body>
${opts.body}
${state}
${scripts.join("\n")}
</body>
</html>`;
}

