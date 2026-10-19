// Hand-off to the real asset editors (Blender, GIMP, Godot) and the credits page.
import { execFile, spawn } from "child_process";
import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { Factory, activeResource, errorText } from "./context";
import { blenderArgs } from "./core/blender";

const BLENDER = ["/Applications/Blender.app/Contents/MacOS/Blender"];
const GIMP = ["/Applications/GIMP.app", "/Applications/GIMP-3.app", "/Applications/GIMP-2.10.app"];
const GODOT = ["/Applications/Godot.app/Contents/MacOS/Godot", "/Applications/Godot_mono.app/Contents/MacOS/Godot"];

function first(paths: string[]): string | undefined {
  return paths.find((p) => fs.existsSync(p));
}

function detached(cmd: string, args: string[]) {
  const child = spawn(cmd, args, { detached: true, stdio: "ignore" });
  child.on("error", (e) => vscode.window.showErrorMessage(`Could not start ${path.basename(cmd)}: ${e.message}`));
  child.unref();
}

function target(uri?: vscode.Uri): string | undefined {
  return (uri ?? activeResource())?.fsPath;
}

export function openInBlender(uri?: vscode.Uri) {
  const file = target(uri);
  const blender = first([process.env.AEN_BLENDER ?? "", ...BLENDER]);
  if (!file) return;
  if (!blender) return void vscode.window.showWarningMessage("Blender was not found in /Applications (or AEN_BLENDER).");
  detached(blender, blenderArgs(file));
}

export function openInGimp(uri?: vscode.Uri) {
  const file = target(uri);
  const gimp = first(GIMP);
  if (!file) return;
  if (!gimp) return void vscode.window.showWarningMessage("GIMP was not found in /Applications.");
  detached("/usr/bin/open", ["-a", gimp, file]);
}

export function openInGodot(uri?: vscode.Uri) {
  const file = target(uri);
  const godot = first(GODOT);
  if (!file) return;
  if (!godot) return void vscode.window.showWarningMessage("Godot was not found in /Applications.");
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
  execFile(path.join(home, "bin", "aen"), ["library", "credits", project, "--write", out], { timeout: 60_000 }, async (err, _stdout, stderr) => {
    if (err) return void vscode.window.showErrorMessage(`Credits: ${stderr.trim() || errorText(err)}`);
    await vscode.commands.executeCommand("vscode.open", vscode.Uri.file(out));
  });
}
