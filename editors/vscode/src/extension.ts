// Aeneas Factory for VS Code (and Cursor, Windsurf, VSCodium): a thin client over the factory service.
import * as vscode from "vscode";
import { openInBlender, openInGimp, openInGodot, writeCredits } from "./apps";
import { Commands, openResult } from "./commands";
import { Factory } from "./context";
import { Job } from "./core/service";
import { Jobs } from "./jobs";
import { LibraryView } from "./libraryView";
import { Preview } from "./preview";
import { ProvenanceView } from "./provenanceView";
import { AudioViewer, GlbViewer } from "./viewers";

export interface Api {
  factory: Factory;
  jobs: Jobs;
  preview: Preview;
  commands: Commands;
}

export function activate(context: vscode.ExtensionContext): Api {
  const factory = new Factory(context.extensionUri, context.extension.packageJSON.aeneas?.minimumFactory);
  const jobs = new Jobs(factory);
  const commands = new Commands(factory, jobs);
  const preview = new Preview(factory, jobs);
  const provenance = new ProvenanceView(factory, commands);
  const jobsView = vscode.window.createTreeView("aeneas.jobs", { treeDataProvider: jobs });
  jobs.attach(jobsView);
  context.subscriptions.push(preview.onDidRender.event((r) => provenance.refresh(r.source)));

  const command = (id: string, fn: (...args: any[]) => unknown) => vscode.commands.registerCommand(id, fn);
  context.subscriptions.push(
    factory.log,
    jobs,
    jobsView,
    preview,
    vscode.window.registerWebviewViewProvider("aeneas.provenance", provenance),
    vscode.window.registerWebviewViewProvider("aeneas.library", new LibraryView(factory), { webviewOptions: { retainContextWhenHidden: true } }),
    vscode.window.registerCustomEditorProvider(GlbViewer.viewType, new GlbViewer(factory), { supportsMultipleEditorsPerDocument: true }),
    vscode.window.registerCustomEditorProvider(AudioViewer.viewType, new AudioViewer(factory), { supportsMultipleEditorsPerDocument: true }),
    command("aeneas.menu", () => commands.menu()),
    command("aeneas.generateImage", () => commands.generateImage()),
    command("aeneas.editImage", (uri?: vscode.Uri) => commands.editImage(uri)),
    command("aeneas.makeTexture", () => commands.makeTexture()),
    command("aeneas.imageTo3d", (uri?: vscode.Uri) => commands.imageTo3d(uri)),
    command("aeneas.generateSound", () => commands.generateSound()),
    command("aeneas.generateSpeech", () => commands.generateSpeech()),
    command("aeneas.upscale", (uri?: vscode.Uri) => commands.upscale(uri)),
    command("aeneas.removeBackground", (uri?: vscode.Uri) => commands.removeBackground(uri)),
    command("aeneas.runRecipe", () => commands.runRecipe()),
    command("aeneas.render", (uri?: vscode.Uri) => preview.renderToAsset(uri)),
    command("aeneas.openPreview", (uri?: vscode.Uri) => preview.open(uri)),
    command("aeneas.showProvenance", (uri?: vscode.Uri) => provenance.show(uri)),
    command("aeneas.openInBlender", (uri?: vscode.Uri) => openInBlender(factory, uri)),
    command("aeneas.openInGimp", (uri?: vscode.Uri) => openInGimp(factory, uri)),
    command("aeneas.openInGodot", (uri?: vscode.Uri) => openInGodot(factory, uri)),
    command("aeneas.refreshJobs", () => jobs.refresh()),
    command("aeneas.cancelJob", (item: any) => jobs.cancel(item)),
    command("aeneas.openJobResult", (job: Job) => openResult(job)),
    command("aeneas.credits", () => writeCredits(factory)),
    command("aeneas.showLog", () => factory.log.show()),
  );
  return { factory, jobs, preview, commands };
}

export function deactivate() {}
