// Hand-off to the real asset editors (Blender, GIMP, Godot) and the credits page.
import { execFile, spawn } from "child_process";
import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { Factory, activeResource, errorText } from "./context";
import { blenderArgs } from "./core/blender";
import { factoryPython } from "./core/service";

/** Where the factory finds an app on this machine (`aen where NAME`), so the paths live in one place. */
function where(factory: Factory, name: string): Promise<string | undefined> {
  const home = factory.factoryPath();
  if (!home) return Promise.resolve(undefined);
  return new Promise((resolve) =>
    execFile(factoryPython(home), ["-m", "aeneas", "where", name], { cwd: home, timeout: 20_000, windowsHide: true },
      (err, stdout) => resolve(err ? undefined : stdout.trim() || undefined)));
}

function detached(cmd: string, args: string[]) {
  const child = spawn(cmd, args, { detached: true, stdio: "ignore", windowsHide: false });
  child.on("error", (e) => vscode.window.showErrorMessage(`Could not start ${path.basename(cmd)}: ${e.message}`));
  child.unref();
}

function target(uri?: vscode.Uri): string | undefined {
  return (uri ?? activeResource())?.fsPath;
}

export async function openInBlender(factory: Factory, uri?: vscode.Uri) {
  const file = target(uri);
  if (!file) return;
  const blender = process.env.AEN_BLENDER || (await where(factory, "blender"));
  if (!blender) return void vscode.window.showWarningMessage("Blender was not found (install it from blender.org, or set AEN_BLENDER).");
  detached(blender, blenderArgs(file));
}

export async function openInGimp(factory: Factory, uri?: vscode.Uri) {
  const file = target(uri);
  if (!file) return;
  const gimp = await where(factory, "gimp-app");
  if (!gimp) return void vscode.window.showWarningMessage("GIMP was not found (install it from gimp.org).");
  if (process.platform === "darwin") detached("/usr/bin/open", ["-a", gimp, file]);
  else detached(gimp, [file]);
}

export async function openInGodot(factory: Factory, uri?: vscode.Uri) {
  const file = target(uri);
  if (!file) return;
  const godot = await where(factory, "godot");
  if (!godot) return void vscode.window.showWarningMessage("Godot was not found (install it from godotengine.org).");
  let dir = path.dirname(file);
  while (!fs.existsSync(path.join(dir, "project.godot")) && path.dirname(dir) !== dir) dir = path.dirname(dir);
  if (!fs.existsSync(path.join(dir, "project.godot"))) return void vscode.window.showWarningMessage("No project.godot above this file.");
  detached(godot, ["--editor", "--path", dir]);
}

/** Write CREDITS.md for the project from everything generated and imported into the library. */
export async function writeCredits(factory: Factory) {
  const project = await factory.requireProject();
  const home = factory.factoryPath();
  if (!project) return;
  if (!home) return void vscode.window.showErrorMessage("The factory was not found; set aeneas.factoryPath.");
  const out = path.join(project, "CREDITS.md");
  if (fs.existsSync(out)) {
    const ok = await vscode.window.showWarningMessage("CREDITS.md exists. Replace it with a fresh one from the library?", { modal: true }, "Replace");
    if (ok !== "Replace") return;
  }
  execFile(factoryPython(home), ["-m", "aeneas", "library", "credits", project, "--write", out], { cwd: home, timeout: 60_000, windowsHide: true }, async (err, _stdout, stderr) => {
    if (err) return void vscode.window.showErrorMessage(`Credits: ${stderr.trim() || errorText(err)}`);
    await vscode.commands.executeCommand("vscode.open", vscode.Uri.file(out));
  });
}
