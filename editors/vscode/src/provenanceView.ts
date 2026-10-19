// The Provenance view: follows the active file and shows how it was made, from its record: models and
// licences, prompt, seed, settings, checks, credits, and for written sources the source itself.
import { createHash } from "crypto";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import * as vscode from "vscode";
import { Commands } from "./commands";
import { Factory, activeResource } from "./context";
import { recordFor, remakeSpec, summarize, Summary } from "./core/provenance";
import { esc, page } from "./webview";

function sha256(file: string): string | undefined {
  try {
    return createHash("sha256").update(fs.readFileSync(file)).digest("hex");
  } catch {
    return undefined;
  }
}

function preview(file: string): string | undefined {
  const p = path.parse(file);
  const ext = p.ext.toLowerCase();
  const options = ext === ".png" || ext === ".jpg" || ext === ".webp" ? [file]
    : ext === ".wav" ? [path.join(p.dir, `${p.name}_wave.png`)]
    : ext === ".glb" ? [path.join(p.dir, `${p.name}_preview.png`)]
    : [];
  return options.find((o) => fs.existsSync(o));
}

const rows = (pairs: Array<[string, string]>) => pairs.map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join("");

export class ProvenanceView implements vscode.WebviewViewProvider {
  private view: vscode.WebviewView | undefined;
  private current: vscode.Uri | undefined;
  private summary: Summary | undefined;

  constructor(private readonly factory: Factory, private readonly commands: Commands) {
    vscode.window.tabGroups.onDidChangeTabs(() => this.follow());
    vscode.window.onDidChangeActiveTextEditor(() => this.follow());
  }

  resolveWebviewView(view: vscode.WebviewView) {
    this.view = view;
    view.webview.options = { enableScripts: true, localResourceRoots: [vscode.Uri.joinPath(this.factory.extensionUri, "media"), vscode.Uri.file(os.homedir())] };
    view.webview.onDidReceiveMessage((m) => this.message(m));
    view.onDidChangeVisibility(() => view.visible && this.render());
    this.current ??= activeResource();
    this.render();
  }

  /** "Show Provenance": show this file's record and bring the view forward. */
  async show(uri?: vscode.Uri) {
    this.current = uri ?? activeResource();
    await vscode.commands.executeCommand("aeneas.provenance.focus");
    this.render();
  }

  /** A render just wrote a record: draw again if the view shows that source, or a file still without a record. */
  refresh(source: string) {
    const shown = this.current?.fsPath;
    if (shown && (shown === source || !this.summary)) this.render();
  }

  private follow() {
    const uri = activeResource();
    if (uri && uri.scheme === "file" && uri.toString() !== this.current?.toString()) {
      this.current = uri;
      this.render();
    }
  }

  private message(m: any) {
    const s = this.summary;
    if (!s || typeof m?.type !== "string") return;
    if (m.type === "openRecord") void vscode.commands.executeCommand("vscode.open", vscode.Uri.file(s.recordPath));
    if (m.type === "openFile") void vscode.commands.executeCommand("vscode.open", vscode.Uri.file(s.file));
    if (m.type === "reveal") void vscode.commands.executeCommand("revealInExplorer", vscode.Uri.file(s.file));
    if (m.type === "copyPrompt" && s.prompt) void vscode.env.clipboard.writeText(s.prompt).then(() => vscode.window.setStatusBarMessage("Prompt copied", 2000));
    if (m.type === "copyCredits") void vscode.env.clipboard.writeText(this.creditText(s)).then(() => vscode.window.setStatusBarMessage("Credit line copied", 2000));
    if (m.type === "remake") {
      const spec = remakeSpec(s);
      if (spec) void this.commands.submit(spec.op, spec.args);
    }
  }

  private creditText(s: Summary): string {
    const models = s.models.map((m) => `${m.name} (${m.licence})`).join(", ");
    return [`${path.basename(s.file)}: made with Aeneas Factory${models ? ` using ${models}` : ""}.`, ...s.credits].join(" ");
  }

  private render() {
    if (!this.view?.visible) return;
    const w = this.view.webview;
    const file = this.current?.fsPath;
    const rec = file ? recordFor(file) : undefined;
    this.summary = undefined;
    let body: string;
    if (!file) {
      body = `<p class="muted">Open a generated file to see how it was made.</p>`;
    } else if (!rec) {
      body = `<p><strong>${esc(path.basename(file))}</strong></p><p class="muted">No provenance record: this file was not made by the factory, or its <code>.json</code> was not kept beside it.</p>`;
    } else {
      try {
        const s = (this.summary = summarize(rec, sha256));
        body = this.html(w, s);
      } catch (e) {
        body = `<p class="error">Could not read ${esc(path.basename(rec))}: ${esc(e instanceof Error ? e.message : e)}</p>`;
      }
    }
    w.html = page(w, this.factory.extensionUri, { title: "Provenance", body: `<div class="side">${body}</div>`, scripts: ["provenance.js"] });
  }

  private html(w: vscode.Webview, s: Summary): string {
    const pic = preview(s.file);
    const isImage = /\.(png|jpe?g|webp)$/i.test(s.file);
    const tile = s.params.some(([k, v]) => k === "tile" && v === "true");
    const verified = s.verified === undefined ? "" : s.verified
      ? `<span class="chip ok" title="The file's SHA-256 matches its record">unchanged since made</span>`
      : `<span class="chip warn" title="The file's SHA-256 differs from its record">changed since made</span>`;
    const models = s.models.map((m) => `
      <div class="model">
        <div><strong>${m.upstream ? `<a href="${esc(m.upstream)}">${esc(m.name)}</a>` : esc(m.name)}</strong></div>
        <div class="muted">${esc(m.licence)}</div>
        ${m.commercial ? `<div class="small">commercial use: ${esc(m.commercial)}</div>` : ""}
        ${m.attribution ? `<div class="small warn-text">credit required: ${esc(m.attribution)}</div>` : ""}
      </div>`).join("");
    const remake = remakeSpec(s) ? `<button data-msg="remake" title="Same prompt and settings, a new seed">Make another</button>` : "";
    return `
      <p class="file"><a href="#" data-msg="openFile">${esc(path.basename(s.file))}</a> ${verified}</p>
      ${pic ? `<div class="thumb${isImage && tile ? " tiled" : ""}" ${isImage && tile ? `data-tile="${esc(w.asWebviewUri(vscode.Uri.file(pic)))}"` : ""}>${isImage && tile ? "" : `<img src="${w.asWebviewUri(vscode.Uri.file(pic))}" alt="">`}</div>` : ""}
      <div class="buttons">${remake}${s.prompt ? `<button data-msg="copyPrompt">Copy prompt</button>` : ""}<button data-msg="copyCredits">Copy credit line</button><button data-msg="openRecord">Open record</button></div>
      <h3>Made with</h3>
      <p>${esc(s.madeWith)}${s.seconds !== undefined ? ` <span class="muted">in ${esc(s.seconds)} s</span>` : ""}${s.created ? `<br><span class="muted">${esc(s.created.replace("T", " "))}</span>` : ""}</p>
      ${s.prompt ? `<h3>Prompt</h3><p class="prompt">${esc(s.prompt)}</p>` : ""}
      ${s.negative ? `<h3>Negative prompt</h3><p class="prompt">${esc(s.negative)}</p>` : ""}
      ${s.source ? `<h3>Source</h3><pre>${esc(s.source)}</pre>` : ""}
      ${s.models.length ? `<h3>Models</h3>${models}` : ""}
      ${s.credits.length ? `<h3>Credit</h3>${s.credits.map((c) => `<p class="warn-text">${esc(c)}</p>`).join("")}` : ""}
      ${s.seed !== undefined && s.seed !== null || s.params.length ? `<h3>Settings</h3><table>${rows([...(s.seed !== undefined && s.seed !== null ? [["seed", String(s.seed)] as [string, string]] : []), ...s.params])}</table>` : ""}
      ${s.selection ? `<p class="muted">${esc(s.selection)}</p>` : ""}
      ${s.checks.length ? `<h3>Checks passed</h3><table>${rows(s.checks)}</table>` : ""}
      ${s.inputs.length ? `<h3>Inputs</h3>${s.inputs.map((i) => `<p class="mono">${esc(i)}</p>`).join("")}` : ""}
      ${s.policy ? `<h3>Licence policy</h3><p class="small">${esc(s.policy)}</p>` : ""}
      ${s.versions.length ? `<h3>Versions</h3><table>${rows(s.versions)}</table>` : ""}`;
  }
}
