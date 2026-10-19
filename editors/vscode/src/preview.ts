// Live rendering: diagrams, SVG, ABC music and Ink/Yarn dialogue are rendered next to their source when
// saved (on the service's light lane, so never behind a GPU job) and shown in a preview beside the editor.
// Saves render without adding to the asset library; "Render Source to Asset" adds the result to it.
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import * as vscode from "vscode";
import { Factory, errorText, isUnderHome } from "./context";
import { errorLine, problemText, renderTarget, RenderTarget } from "./core/outputs";
import { Jobs } from "./jobs";
import { page } from "./webview";

interface Rendered {
  source: string;
  target: RenderTarget;
  status: "rendering" | "done" | "failed";
  error?: string;
  seconds?: number;
  at: number;
}

export class Preview implements vscode.Disposable {
  private panel: vscode.WebviewPanel | undefined;
  private showing: string | undefined;
  private readonly last = new Map<string, Rendered>();
  private readonly running = new Map<string, Promise<void>>();
  private readonly again = new Set<string>();
  private readonly problems = vscode.languages.createDiagnosticCollection("aeneas");
  private readonly subs: vscode.Disposable[] = [];
  /** For tests: resolves after each render settles. */
  readonly onDidRender = new vscode.EventEmitter<Rendered>();

  constructor(private readonly factory: Factory, private readonly jobs: Jobs) {
    this.subs.push(
      vscode.workspace.onDidSaveTextDocument((doc) => {
        if (this.factory.config.get<boolean>("renderOnSave") && renderTarget(doc.fileName, "") && isUnderHome(doc.fileName)) {
          void this.render(doc.fileName, doc.getText(), false);
        }
      }),
      vscode.window.onDidChangeActiveTextEditor((ed) => {
        const f = ed?.document.fileName;
        if (this.panel && f && renderTarget(f, "") && f !== this.showing) {
          this.showing = f;
          if (this.last.has(f)) this.update();
          else void this.render(f, ed!.document.getText(), false);
        }
      }),
      this.problems,
      this.onDidRender,
    );
  }

  /** "Open Preview to the Side": render the active source now and show it. */
  async open(uri?: vscode.Uri) {
    const file = uri?.fsPath ?? vscode.window.activeTextEditor?.document.fileName;
    if (!file || !renderTarget(file, "")) {
      vscode.window.showInformationMessage("Aeneas previews .dot, .gv, .d2, .mmd, .vl.json, .svg, .abc, .ink and .yarn files.");
      return;
    }
    this.ensurePanel();
    this.showing = file;
    if (this.running.has(file)) return this.running.get(file); // switching to the file already started one
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(file));
    await this.render(file, doc.getText(), false);
  }

  /** "Render Source to Asset": render and add the result to the asset library. */
  async renderToAsset(uri?: vscode.Uri) {
    const file = uri?.fsPath ?? vscode.window.activeTextEditor?.document.fileName;
    if (!file || !renderTarget(file, "")) {
      vscode.window.showInformationMessage("Pick a diagram, SVG, ABC, Ink or Yarn source to render.");
      return;
    }
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(file));
    if (doc.isDirty) await doc.save();
    await this.render(file, doc.getText(), true);
    const r = this.last.get(file);
    if (r?.status === "done") {
      const pick = await vscode.window.showInformationMessage(`Rendered ${path.basename(r.target.out)} (added to the library)`, "Open", "Show Provenance");
      if (pick === "Open") await vscode.commands.executeCommand("vscode.open", vscode.Uri.file(r.target.out));
      if (pick === "Show Provenance") await vscode.commands.executeCommand("aeneas.showProvenance", vscode.Uri.file(r.target.out));
    } else if (r?.status === "failed") {
      vscode.window.showErrorMessage(`Aeneas: ${r.error}`);
    }
  }

  /** Render one source; a save during a render queues exactly one more. */
  render(file: string, text: string, library: boolean): Promise<void> {
    if (this.running.has(file)) {
      this.again.add(file);
      return this.running.get(file)!;
    }
    const run = this.renderOnce(file, text, library).finally(async () => {
      this.running.delete(file);
      if (this.again.delete(file)) {
        const doc = vscode.workspace.textDocuments.find((d) => d.fileName === file);
        await this.render(file, doc?.getText() ?? fs.readFileSync(file, "utf8"), library);
      }
    });
    this.running.set(file, run);
    return run;
  }

  private async renderOnce(file: string, text: string, library: boolean) {
    if (!text.trim()) return; // a new, empty file: nothing to render yet
    const target = renderTarget(file, text)!;
    const state: Rendered = { source: file, target, status: "rendering", at: Date.now() };
    this.last.set(file, state);
    if (this.showing === file) this.update();
    try {
      const client = await this.factory.client();
      const job = await client.submitOp(target.op, target.args, { library });
      this.jobs.track(job);
      const done = await client.wait(job.id);
      state.status = done.status === "done" ? "done" : "failed";
      state.error = done.error ?? (done.status === "cancelled" ? "cancelled" : undefined);
      state.seconds = done.finished && done.started ? done.finished - done.started : undefined;
    } catch (e) {
      state.status = "failed";
      state.error = errorText(e);
    }
    state.at = Date.now();
    this.setProblems(file, state);
    if (this.showing === file) this.update();
    if (state.status === "failed") this.factory.log.warn(`render ${path.basename(file)}: ${state.error}`);
    this.onDidRender.fire(state);
  }

  private setProblems(file: string, r: Rendered) {
    const uri = vscode.Uri.file(file);
    if (r.status !== "failed" || !r.error) {
      this.problems.delete(uri);
      return;
    }
    const line = errorLine(r.error) ?? 0;
    const d = new vscode.Diagnostic(new vscode.Range(line, 0, line, Number.MAX_SAFE_INTEGER), problemText(r.error, path.basename(file)), vscode.DiagnosticSeverity.Error);
    d.source = "aeneas";
    this.problems.set(uri, [d]);
  }

  private ensurePanel() {
    if (this.panel) {
      this.panel.reveal(vscode.ViewColumn.Beside, true);
      return;
    }
    const roots = [vscode.Uri.joinPath(this.factory.extensionUri, "media"), vscode.Uri.file(os.homedir())];
    this.panel = vscode.window.createWebviewPanel("aeneas.preview", "Aeneas Preview", { viewColumn: vscode.ViewColumn.Beside, preserveFocus: true },
      { enableScripts: true, localResourceRoots: roots });
    this.panel.iconPath = vscode.Uri.joinPath(this.factory.extensionUri, "media", "activity.svg");
    this.panel.webview.html = page(this.panel.webview, this.factory.extensionUri, {
      title: "Aeneas Preview",
      body: `<main id="preview" class="preview"><p class="muted">Save a diagram, SVG, ABC, Ink or Yarn file to render it.</p></main>`,
      scripts: ["preview.js"],
    });
    this.panel.webview.onDidReceiveMessage((m) => {
      if (m?.type === "open" && typeof m.path === "string" && this.isKnownOutput(m.path)) {
        void vscode.commands.executeCommand("vscode.open", vscode.Uri.file(m.path));
      } else if (m?.type === "provenance" && typeof m.path === "string" && this.isKnownOutput(m.path)) {
        void vscode.commands.executeCommand("aeneas.showProvenance", vscode.Uri.file(m.path));
      } else if (m?.type === "ready") {
        this.update();
      }
    });
    this.panel.onDidDispose(() => (this.panel = undefined));
  }

  private isKnownOutput(p: string): boolean {
    return [...this.last.values()].some((r) => r.target.out === p || r.source === p);
  }

  private update() {
    if (!this.panel || !this.showing) return;
    const r = this.last.get(this.showing);
    if (!r) return;
    const w = this.panel.webview;
    const out = r.target.out;
    const version = `?v=${r.at}`;
    const wave = out.replace(/\.wav$/, "_wave.png");
    let size: number | undefined;
    try {
      size = fs.statSync(out).size;
    } catch {
      /* not made yet */
    }
    this.panel.title = `Preview ${path.basename(r.source)}`;
    void w.postMessage({
      type: "show",
      source: path.basename(r.source),
      status: r.status,
      error: r.error,
      seconds: r.seconds,
      kind: r.target.kind,
      out,
      outName: path.basename(out),
      size,
      image: r.target.kind === "image" && size ? w.asWebviewUri(vscode.Uri.file(out)).toString() + version : undefined,
      audio: r.target.kind === "audio" && size ? w.asWebviewUri(vscode.Uri.file(out)).toString() + version : undefined,
      wave: r.target.kind === "audio" && fs.existsSync(wave) ? w.asWebviewUri(vscode.Uri.file(wave)).toString() + version : undefined,
    });
  }

  dispose() {
    this.panel?.dispose();
    this.subs.forEach((s) => s.dispose());
  }
}
