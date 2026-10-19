// The Library view: search everything generated and every imported pack (words, and for images their
// meaning when the scoring model is installed), filter by kind, licence and project, open or reveal.
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import * as vscode from "vscode";
import { Factory, errorText } from "./context";
import { LibraryEntry } from "./core/service";
import { page } from "./webview";

function thumbnail(p: string): string | undefined {
  const x = path.parse(p);
  const ext = x.ext.toLowerCase();
  const options = [".png", ".jpg", ".jpeg", ".webp", ".gif"].includes(ext) ? [p]
    : ext === ".wav" || ext === ".ogg" || ext === ".mp3" ? [path.join(x.dir, `${x.name}_wave.png`)]
    : ext === ".glb" || ext === ".gltf" ? [path.join(x.dir, `${x.name}_preview.png`)]
    : [];
  return options.find((o) => fs.existsSync(o));
}

export class LibraryView implements vscode.WebviewViewProvider {
  private view: vscode.WebviewView | undefined;
  private shown = new Set<string>();

  constructor(private readonly factory: Factory) {}

  resolveWebviewView(view: vscode.WebviewView) {
    this.view = view;
    view.webview.options = { enableScripts: true, localResourceRoots: [vscode.Uri.joinPath(this.factory.extensionUri, "media"), vscode.Uri.file(os.homedir())] };
    view.webview.html = page(view.webview, this.factory.extensionUri, {
      title: "Library",
      body: `
<div class="side library">
  <form id="search" class="search">
    <input id="q" type="search" placeholder="Search: mossy stone, door creak…" aria-label="Search the asset library">
    <div class="filters">
      <select id="kind" aria-label="Kind"><option value="">any kind</option><option value="image">images</option><option value="audio">sound</option><option value="model">3D</option><option value="motion">motion</option><option value="font">fonts</option><option value="other">other</option></select>
      <select id="origin" aria-label="Origin"><option value="">made or downloaded</option><option value="generated">made here</option><option value="downloaded">downloaded</option></select>
      <input id="licence" placeholder="licence, e.g. CC0" aria-label="Licence">
      <label class="small"><input type="checkbox" id="here" checked> this project</label>
    </div>
  </form>
  <div id="status" class="muted small"></div>
  <div id="results" class="grid"></div>
</div>`,
      scripts: ["library.js"],
    });
    view.webview.onDidReceiveMessage((m) => this.message(m));
  }

  private async message(m: any) {
    if (m?.type === "search") return this.search(m);
    if ((m?.type === "open" || m?.type === "reveal" || m?.type === "provenance") && typeof m.path === "string" && this.shown.has(m.path)) {
      const uri = vscode.Uri.file(m.path);
      const command = m.type === "open" ? "vscode.open" : m.type === "reveal" ? "revealFileInOS" : "aeneas.showProvenance";
      await vscode.commands.executeCommand(command, uri);
    }
  }

  private async search(m: { q?: string; kind?: string; licence?: string; origin?: string; here?: boolean }) {
    const w = this.view?.webview;
    if (!w) return;
    try {
      const client = await this.factory.client();
      const project = m.here ? this.factory.project() : undefined;
      const rows: LibraryEntry[] = await client.library({ q: m.q, kind: m.kind, licence: m.licence, origin: m.origin, project, limit: 60 });
      this.shown = new Set(rows.map((r) => r.path));
      const items = rows.map((r) => {
        const t = thumbnail(r.path);
        return {
          path: r.path,
          name: path.basename(r.path),
          kind: r.kind,
          licence: r.licence || (r.origin === "generated" ? "see record" : "unknown"),
          origin: r.origin,
          source: r.source,
          prompt: r.prompt,
          exists: fs.existsSync(r.path),
          thumb: t ? w.asWebviewUri(vscode.Uri.file(t)).toString() : undefined,
        };
      });
      void w.postMessage({ type: "results", items, project: project ? path.basename(project) : undefined });
    } catch (e) {
      void w.postMessage({ type: "error", message: errorText(e) });
    }
  }
}
