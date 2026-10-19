// Read-only viewers for .glb (three.js: orbit, wireframe, real size) and .wav (waveform, play, loudness),
// each with the asset's provenance underneath.
import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { Factory } from "./context";
import { recordFor, summarize } from "./core/provenance";
import { esc, page } from "./webview";

class Doc implements vscode.CustomDocument {
  constructor(readonly uri: vscode.Uri) {}
  dispose() {}
}

function recordChips(file: string): string {
  const rec = recordFor(file);
  if (!rec) return `<p class="muted">No provenance record beside this file.</p>`;
  try {
    const s = summarize(rec);
    const chips = [
      s.madeWith && `<span class="chip">${esc(s.madeWith)}</span>`,
      ...s.models.map((m) => `<span class="chip" title="${esc(m.licence)}">${esc(m.name)}</span>`),
      s.seed !== undefined && s.seed !== null && `<span class="chip">seed ${esc(s.seed)}</span>`,
      s.seconds !== undefined && `<span class="chip">${esc(s.seconds)} s</span>`,
      ...s.credits.map((c) => `<span class="chip warn">${esc(c)}</span>`),
    ].filter(Boolean);
    return `<div class="chips">${chips.join("")}</div>${s.prompt ? `<p class="prompt">${esc(s.prompt)}</p>` : ""}`;
  } catch {
    return "";
  }
}

abstract class Viewer implements vscode.CustomReadonlyEditorProvider<Doc> {
  constructor(protected readonly factory: Factory) {}

  openCustomDocument(uri: vscode.Uri): Doc {
    return new Doc(uri);
  }

  resolveCustomEditor(doc: Doc, panel: vscode.WebviewPanel): void {
    const dir = vscode.Uri.file(path.dirname(doc.uri.fsPath));
    panel.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(this.factory.extensionUri, "media"), vscode.Uri.joinPath(this.factory.extensionUri, "dist"), dir],
    };
    const render = () => (panel.webview.html = this.html(panel.webview, doc.uri));
    render();
    // Re-render when the file is remade (a new seed, a new LOD), with a fresh URL so nothing is cached.
    const watcher = vscode.workspace.createFileSystemWatcher(new vscode.RelativePattern(dir, path.basename(doc.uri.fsPath)));
    watcher.onDidChange(render);
    panel.onDidDispose(() => watcher.dispose());
    panel.webview.onDidReceiveMessage((m) => {
      if (m?.type === "command" && ["aeneas.showProvenance", "aeneas.openInBlender", "revealInExplorer"].includes(m.command)) {
        void vscode.commands.executeCommand(m.command, doc.uri);
      }
    });
  }

  protected fileUrl(webview: vscode.Webview, uri: vscode.Uri): string {
    let stamp = 0;
    try {
      stamp = fs.statSync(uri.fsPath).mtimeMs;
    } catch {
      /* gone */
    }
    return `${webview.asWebviewUri(uri)}?v=${stamp}`;
  }

  protected abstract html(webview: vscode.Webview, uri: vscode.Uri): string;
}

export class GlbViewer extends Viewer {
  static readonly viewType = "aeneas.glb";

  protected html(webview: vscode.Webview, uri: vscode.Uri): string {
    return page(webview, this.factory.extensionUri, {
      title: path.basename(uri.fsPath),
      body: `
<div class="viewer">
  <div class="toolbar">
    <strong>${esc(path.basename(uri.fsPath))}</strong>
    <span class="spacer"></span>
    <label><input type="checkbox" id="wire"> wireframe</label>
    <label><input type="checkbox" id="grid" checked> grid</label>
    <label><input type="checkbox" id="spin"> turn</label>
    <button id="reset" title="Frame the model">Frame</button>
    <button data-command="aeneas.openInBlender">Open in Blender</button>
    <button data-command="aeneas.showProvenance">Provenance</button>
  </div>
  <div id="stage" class="stage" data-src="${esc(this.fileUrl(webview, uri))}"><p class="muted center" id="loading">Loading…</p></div>
  <div class="stats" id="stats"></div>
  <div class="record">${recordChips(uri.fsPath)}</div>
</div>`,
      scripts: ["viewer-common.js", "glb-viewer.js"],
      wasm: true, // the meshopt decoder (gltfpack -cc) is WebAssembly
    });
  }
}

export class AudioViewer extends Viewer {
  static readonly viewType = "aeneas.audio";

  protected html(webview: vscode.Webview, uri: vscode.Uri): string {
    return page(webview, this.factory.extensionUri, {
      title: path.basename(uri.fsPath),
      body: `
<div class="viewer">
  <div class="toolbar">
    <strong>${esc(path.basename(uri.fsPath))}</strong>
    <span class="spacer"></span>
    <button id="play" title="Play or pause (space)">Play</button>
    <label><input type="checkbox" id="loop"> loop</label>
    <button data-command="aeneas.showProvenance">Provenance</button>
    <button data-command="revealInExplorer">Reveal</button>
  </div>
  <div class="wave-wrap"><canvas id="wave" data-src="${esc(this.fileUrl(webview, uri))}"></canvas><div id="playhead" class="playhead"></div></div>
  <div class="stats" id="stats"><span class="muted">Decoding…</span></div>
  <div class="record">${recordChips(uri.fsPath)}</div>
</div>`,
      scripts: ["viewer-common.js", "audio-viewer.js"],
    });
  }
}
