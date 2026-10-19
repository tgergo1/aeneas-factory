// What every part of the extension shares: settings, the service connection and the current project.
import * as os from "os";
import * as path from "path";
import * as vscode from "vscode";
import { Client, connect, ensureRunning, findFactory, olderThan } from "./core/service";

export class Factory {
  readonly log = vscode.window.createOutputChannel("Aeneas Factory", { log: true });

  private warnedAbout: string | undefined;

  constructor(readonly extensionUri: vscode.Uri, readonly minimumFactory = "0.0.0") {}

  /** Warn once when the running service is older than this extension needs. */
  noteVersion(version: string) {
    if (!olderThan(version, this.minimumFactory) || this.warnedAbout === version) return;
    this.warnedAbout = version;
    this.log.warn(`factory service ${version} is older than ${this.minimumFactory}`);
    void vscode.window.showWarningMessage(
      `The Aeneas Factory service is version ${version}; this extension needs ${this.minimumFactory} or later. ` +
        "Live previews may wait behind GPU jobs and be added to the library. Update the factory (git pull), then restart its service: aen service stop, then aen service start.",
    );
  }

  get config() {
    return vscode.workspace.getConfiguration("aeneas");
  }

  factoryPath(): string | undefined {
    return findFactory(this.config.get<string>("factoryPath"));
  }

  /** The running service, without starting it. */
  running(): Promise<Client | undefined> {
    return connect();
  }

  /** The service, started if needed (it then stops by itself after 30 idle minutes). */
  async client(): Promise<Client> {
    const running = await connect();
    if (running) return running;
    return vscode.window.withProgress(
      { location: vscode.ProgressLocation.Window, title: "Starting the Aeneas Factory service" },
      () => ensureRunning(this.factoryPath()),
    );
  }

  /** The project a command works in: the active file's workspace folder, else the first one. */
  project(resource?: vscode.Uri): string | undefined {
    const uri = resource ?? activeResource();
    const folder = (uri && vscode.workspace.getWorkspaceFolder(uri)) ?? vscode.workspace.workspaceFolders?.[0];
    return folder?.uri.fsPath;
  }

  async requireProject(resource?: vscode.Uri): Promise<string | undefined> {
    const p = this.project(resource);
    if (!p) {
      vscode.window.showWarningMessage("Open a folder first: results go into the project's generated/ folder.");
      return undefined;
    }
    if (!isUnderHome(p)) {
      vscode.window.showWarningMessage(`The factory writes only under your home folder; ${p} is outside it.`);
      return undefined;
    }
    return p;
  }

  outputFolder(): string {
    return this.config.get<string>("outputFolder") || "generated";
  }
}

export function isUnderHome(p: string): boolean {
  const rel = path.relative(os.homedir(), p);
  return !!rel && !rel.startsWith("..") && !path.isAbsolute(rel);
}

/** The file in the active tab: a text editor, or a custom editor such as an image or our viewers. */
export function activeResource(): vscode.Uri | undefined {
  const input = vscode.window.tabGroups.activeTabGroup.activeTab?.input;
  if (input instanceof vscode.TabInputText || input instanceof vscode.TabInputCustom) return input.uri;
  return vscode.window.activeTextEditor?.document.uri;
}

export function errorText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
